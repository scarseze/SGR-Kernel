import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("mcp_client")

class MCPClient:
    """
    Тонкий клиент Model Context Protocol (MCP) через stdio.
    Обеспечивает запуск сторонних плагинов в изолированных процессах 
    через JSON-RPC (stdout/stdin).
    """
    def __init__(self, command: str, args: List[str]):
        self.command = command
        self.args = args
        self.process: Optional[asyncio.subprocess.Process] = None
        self._msg_id = 0
        self._pending_requests: Dict[int, asyncio.Future] = {}
        self._read_task: Optional[asyncio.Task] = None

    async def connect(self):
        """Запускает дочерний процесс (MCP Server)."""
        logger.info(f"Запуск MCP Сервера (изолированно): {self.command} {' '.join(self.args)}")
        self.process = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        self._read_task = asyncio.create_task(self._listen_stdout())
        # MCP requires initialize
        await self._send_request("initialize", {
            "protocolVersion": "2024-11-05", # standard MCP version
            "capabilities": {},
            "clientInfo": {"name": "sgr-kernel-mcp", "version": "3.0.0"}
        })
        # notify that we are initialized
        await self._send_notification("notifications/initialized", {})

    async def _listen_stdout(self):
        """Фоновый таск для чтения ответов MCP-сервера по stdout."""
        if not self.process or not self.process.stdout:
            return
            
        while True:
            try:
                line = await self.process.stdout.readline()
                if not line:
                    break
                
                # MCP usually sends pure JSON per line in stdio transport
                try:
                    msg = json.loads(line.decode('utf-8'))
                    if "id" in msg:
                        # This is a response to our request
                        msg_id = msg["id"]
                        if msg_id in self._pending_requests:
                            if "error" in msg:
                                self._pending_requests.pop(msg_id).set_exception(Exception(str(msg["error"])))
                            else:
                                self._pending_requests.pop(msg_id).set_result(msg.get("result"))
                    elif "method" in msg and msg["method"].startswith("notifications/"):
                        # Server notification, log it
                        logger.debug(f"MCP Наблюдение: {msg}")
                except json.JSONDecodeError:
                    # Ignore non-JSON lines (e.g. random print statements from poor server)
                    pass
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка чтения stdout: {e}")
                break
                
        # If we exit the loop (EOF or error), cancel all pending futures so they don't hang
        for msg_id, future in list(self._pending_requests.items()):
            if not future.done():
                future.set_exception(EOFError("MCP Server closed stdout stream unexpectedly."))
        self._pending_requests.clear()

    async def _send_request(self, method: str, params: Optional[Dict] = None) -> Any:
        self._msg_id += 1
        msg_id = self._msg_id
        
        req = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": method
        }
        if params is not None:
            req["params"] = params
            
        future = asyncio.get_running_loop().create_future()
        self._pending_requests[msg_id] = future
        
        data = json.dumps(req, ensure_ascii=False) + "\n"
        if self.process and self.process.stdin:
            self.process.stdin.write(data.encode('utf-8'))
            await self.process.stdin.drain()
            
        # Ждем ответ
        return await future

    async def _send_notification(self, method: str, params: Optional[Dict] = None):
        req = {
            "jsonrpc": "2.0",
            "method": method
        }
        if params is not None:
            req["params"] = params
            
        data = json.dumps(req, ensure_ascii=False) + "\n"
        if self.process and self.process.stdin:
            self.process.stdin.write(data.encode('utf-8'))
            await self.process.stdin.drain()

    async def get_tools(self) -> List[Dict]:
        """Запрашивает список доступных инструментов у MCP сервера."""
        res = await self._send_request("tools/list")
        return res.get("tools", [])

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Выполняет инструмент в изолированном процессе."""
        res = await self._send_request("tools/call", {
            "name": name,
            "arguments": arguments
        })
        
        # MCP возвращает content как массив
        content = res.get("content", [])
        if content and isinstance(content, list) and len(content) > 0:
            if content[0].get("type") == "text":
                return content[0].get("text")
        
        return str(content)

    async def close(self):
        """Безопасное завершение дочернего процесса."""
        if self._read_task:
            try:
                self._read_task.cancel()
            except Exception:
                pass
        if self.process:
            if self.process.returncode is None:
                self.process.terminate()
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    self.process.kill()
