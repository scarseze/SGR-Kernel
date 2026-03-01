# Deployment Guide (v1.x)

## 1. Local Setup
Ensure you have Python 3.10+ installed.

```bash
# Clone
git clone <repo_url>
cd sgr_kernel

# Virtual Env
python -m venv venv
source venv/bin/activate # or venv\Scripts\activate

# Install
pip install -e .
```

## 2. Docker Deployment
The SGR Kernel is best run as a containerized service.

```bash
# Build
docker build -t sgr-kernel:latest .

# Run
docker run --env-file .env sgr-kernel:latest
```

## 3. Configuration
Use environment variables for core infrastructure:
- `LLM_BASE_URL`: API endpoint for LLM providers.
- `OPENAI_API_KEY`: Secrets management.
- `LOCAL_MODEL`: Local model name via Ollama (e.g. `qwen2.5:1.5b`).
- `OLLAMA_BASE_URL`: API endpoint for Ollama (e.g. `http://localhost:11434` or `http://host.docker.internal:11434`).
- `ARTIFACT_STORAGE_PATH`: Path for CAS artifacts (defaults to `./artifacts`).
- `CHECKPOINT_PATH`: Path for execution states (defaults to `./checkpoints`).

### Important Note on Timeouts
When using slow local models through proxies or `litellm`, the `httpx` or `aiohttp` internal clients may drop connections (e.g., throwing a `502 Bad Gateway` or "Could not reach the server"). The SGR Kernel is pre-configured with a 3600s timeout in `core/swarm.py` and `proxy/main.py` to prevent this. Ensure your reverse proxies (like Nginx) also have extended `proxy_read_timeout` values.

## 4. Production Staging
- **State Persistence**: Ensure the `checkpoints/` directory is mounted as a persistent volume.
- **Telemetry**: Configure `logger.py` to forward logs to a centralized stack (ELK/Graylog).
- **Worker Scaling**: For distributed workloads, use the `Dispatcher` interface to connect remote workers.
