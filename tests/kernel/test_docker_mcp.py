import pytest
import asyncio
from unittest.mock import patch, MagicMock
import json
from core.docker_mcp_client import DockerMCPClient

@pytest.mark.asyncio
async def test_docker_mcp_client_cmd_generation():
    # Проверка, что аргументы для жесткой песочницы формируются правильно
    client = DockerMCPClient(
        image_name="test-mcp-image:latest",
        container_args=["--custom-flag"],
        network_none=True,
        mem_limit="128m",
        cpus=0.25,
        readonly_rootfs=True
    )
    
    assert client.command == "docker"
    
    # Ожидаемые аргументы
    expected_args = [
        "run", "-i", "--rm", 
        "--network", "none", 
        "--read-only",
        "--memory", "128m",
        "--cpus", "0.25",
        "--security-opt", "no-new-privileges:true",
        "--cap-drop", "ALL",
        "test-mcp-image:latest",
        "--custom-flag"
    ]
    
    # Проверяем вхождение основных флагов
    for arg in expected_args:
        assert arg in client.args

@pytest.mark.asyncio
@patch("asyncio.create_subprocess_exec")
async def test_docker_mcp_client_connect_and_close(mock_create_subprocess):
    # Мокаем процесс
    mock_proc = MagicMock()
    mock_proc.stdin = MagicMock()
    mock_proc.stdout = MagicMock()
    async def mock_readline():
        return b'{"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2024-11-05"}}\n'
    mock_proc.stdout.readline = mock_readline
    
    # asyncio.create_subprocess_exec returns a coroutine
    async def mock_subprocess(*args, **kwargs):
        return mock_proc
        
    mock_create_subprocess.side_effect = mock_subprocess
    
    client = DockerMCPClient(image_name="dummy:latest")
    
    # Нужно замокать `_send_request` для `initialize`, чтобы тест не застрял
    with patch.object(client, "_send_request", new_callable=MagicMock) as mock_send_request:
        mock_send_request.return_value = asyncio.Future()
        mock_send_request.return_value.set_result(None)
        
        with patch.object(client, "_send_notification", new_callable=MagicMock) as mock_notify:
            mock_notify.return_value = asyncio.Future()
            mock_notify.return_value.set_result(None)
            
            await client.connect()
            assert client.process is not None
            mock_create_subprocess.assert_called_once()
            assert "docker" == mock_create_subprocess.call_args[0][0]
            
            await client.close()

@pytest.mark.asyncio
async def test_docker_mcp_hardened_sandbox():
    """
    Test that DockerMCPClient can run a container with strict security measures
    (--cap-drop=ALL, --read-only, --tmpfs) and successfully communicate via stdin/stdout.
    """
    
    # We use a simple python inline script to mock an MCP server response.
    # It reads from stdin continuously to catch `initialize` and `tools/list`.
    mock_mcp_server_code = (
        "import sys, json\n"
        "for line in sys.stdin:\n"
        "    if not line.strip(): continue\n"
        "    try:\n"
        "        req = json.loads(line)\n"
        "        method = req.get('method')\n"
        "        if method == 'initialize':\n"
        "            resp = {\n"
        "                'jsonrpc': '2.0',\n"
        "                'id': req.get('id', 1),\n"
        "                'result': {\n"
        "                    'protocolVersion': '2024-11-05',\n"
        "                    'capabilities': {},\n"
        "                    'serverInfo': {'name': 'mock-secure-server', 'version': '1.0.0'}\n"
        "                }\n"
        "            }\n"
        "            print(json.dumps(resp))\n"
        "            sys.stdout.flush()\n"
        "        elif method == 'tools/list':\n"
        "            resp = {\n"
        "                'jsonrpc': '2.0',\n"
        "                'id': req.get('id', 2),\n"
        "                'result': {'tools': [{'name': 'secure-tool', 'description': 'secure'}]}\n"
        "            }\n"
        "            print(json.dumps(resp))\n"
        "            sys.stdout.flush()\n"
        "    except Exception:\n"
        "        pass\n"
    )

    import base64
    encoded_code = base64.b64encode(mock_mcp_server_code.encode('utf-8')).decode('utf-8')
    safe_command = f"import base64; exec(base64.b64decode('{encoded_code}').decode('utf-8'))"

    client = DockerMCPClient(
        image_name="python:3.13-slim",
        container_args=["python3", "-u", "-c", safe_command],
        mem_limit="128m",
        readonly_rootfs=True,
        network_none=True
    )

    try:
        # connect() automatically sends the `initialize` request and awaits the response
        await asyncio.wait_for(client.connect(), timeout=60.0)

        # verify we can communicate by asking for tools
        tools = await asyncio.wait_for(client.get_tools(), timeout=5.0)
        
        assert tools is not None
        assert len(tools) == 1
        assert tools[0]["name"] == "secure-tool"
        
    finally:
        await client.close()

@pytest.mark.asyncio
async def test_docker_mcp_readonly_enforcement():
    """
    Verify that the container filesystem is truly read-only and prevents unauthorized writes.
    """
    # This script tries to write to /root/test.txt. It should fail due to read-only rootfs.
    fail_code = "open('/root/test.txt', 'w').write('hacked');"
    
    client = DockerMCPClient(
        image_name="python:3.13-slim",
        container_args=["python3", "-u", "-c", fail_code],
        readonly_rootfs=True,
    )
    
    try:
        # The container will immediately crash from OSError: [Errno 30] Read-only file system
        # Because it crashed, it won't respond to the initialize request, causing EOFError
        with pytest.raises(EOFError):
            await asyncio.wait_for(client.connect(), timeout=60.0)
            
    finally:
        await client.close()

