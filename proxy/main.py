import os

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response

# Load env vars (including keys mounted via Docker Secrets if routed to env, or direct env)
load_dotenv()

app = FastAPI()

# Configuration
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"  # Target API
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")

if not DEEPSEEK_API_KEY:
    print(f"⚠️ WARNING: DEEPSEEK_API_KEY not found in Proxy environment! Falling back to {OLLAMA_BASE_URL}", flush=True)


@app.middleware("http")
async def health_check_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-SGR-Proxy"] = "Active"
    return response


@app.get("/health")
async def health():
    return {"status": "ok", "key_loaded": bool(DEEPSEEK_API_KEY)}


@app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_request(path: str, request: Request):
    """
    Proxies all /v1/* requests to the target LLM API, injecting the secret key.
    Uses BUFFERED mode (no streaming) to ensure stability.
    """
    # Clean headers, including accept-encoding to handle it completely ourselves
    blacklist = {"host", "content-length", "authorization", "accept-encoding"}
    headers = {k: v for k, v in request.headers.items() if k.lower() not in blacklist}

    # Determine Target
    if DEEPSEEK_API_KEY:
        target_url = f"{DEEPSEEK_BASE_URL}/{path}"
        clean_key = DEEPSEEK_API_KEY.encode("ascii", "ignore").decode("ascii").strip()
        headers["Authorization"] = f"Bearer {clean_key}"
    else:
        # Fallback to Ollama
        target_url = f"{OLLAMA_BASE_URL}/v1/{path}"

    # Disable compression upstream
    headers["Accept-Encoding"] = "identity"

    try:
        # Create a client
        async with httpx.AsyncClient(timeout=3600.0) as client:
            req_body = await request.body()

            req = client.build_request(method=request.method, url=target_url, headers=headers, content=req_body)

            # Send request (Buffered)
            r = await client.send(req)
            # await r.read() # Removed: client.send() without stream=True already reads body

            # Filter response headers
            excluded_headers = {"content-encoding", "content-length", "transfer-encoding", "connection", "host"}
            resp_headers = {k: v for k, v in r.headers.items() if k.lower() not in excluded_headers}

            return Response(
                content=r.content,
                status_code=r.status_code,
                headers=resp_headers,
                media_type=r.headers.get("content-type", "application/json"),
            )

    except Exception as e:
        print(f"Proxy Error: {e}", flush=True)
        raise HTTPException(status_code=502, detail=f"Upstream Error: {e}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
