import json
import sys


def log(msg):
    print(f"DEBUG: {msg}", file=sys.stderr)

def main():
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            
            req = json.loads(line)
            method = req.get("method")
            msg_id = req.get("id")
            
            if method == "initialize":
                res = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "dummy-server", "version": "1.0"}
                    }
                }
                print(json.dumps(res), flush=True)

            elif method == "tools/list":
                res = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "tools": [
                            {
                                "name": "dummy_calculator",
                                "description": "Adds two numbers",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "a": {"type": "integer"},
                                        "b": {"type": "integer"}
                                    },
                                    "required": ["a", "b"]
                                }
                            }
                        ]
                    }
                }
                print(json.dumps(res), flush=True)

            elif method == "tools/call":
                params = req.get("params", {})
                name = params.get("name")
                args = params.get("arguments", {})
                
                if name == "dummy_calculator":
                    result = args.get("a", 0) + args.get("b", 0)
                    res = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": str(result)
                                }
                            ]
                        }
                    }
                    print(json.dumps(res), flush=True)

        except Exception as e:
            log(f"Error handling request: {e}")

if __name__ == "__main__":
    main()
