"""Start the built website and, when needed, its project-local search node."""

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


root = Path.cwd().resolve()
sys.path.insert(0, str(root / "backend"))
import settings


def local_json(url):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(url, timeout=2) as response:
            return json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None


if not (root / "frontend" / "dist" / "index.html").is_file():
    raise SystemExit("请先在 frontend 中运行 npm install 和 npm run build。")

address = f"http://{settings.api_host}:{settings.api_port}"
if local_json(address + "/api/health"):
    raise SystemExit(f"{address} 已有服务运行，请先停止它或修改 API_PORT。")

children = []
try:
    engine = local_json(settings.search_url)
    if settings.search_backend != "sqlite" and engine is None:
        print("Starting project-local OpenSearch...", flush=True)
        service = subprocess.Popen(
            [sys.executable, "scripts/start_search.py"],
            cwd=root,
            start_new_session=True,
        )
        children.append(service)
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            if service.poll() is not None:
                print(
                    "OpenSearch did not start. The application will use local retrieval.",
                    flush=True,
                )
                break
            if local_json(settings.search_url):
                break
            time.sleep(1)
        else:
            raise RuntimeError(
                "OpenSearch 启动超时，请检查 runtime/opensearch-console.log"
            )
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "app:app",
        "--app-dir",
        "backend",
        "--host",
        settings.api_host,
        "--port",
        str(settings.api_port),
    ]
    backend = subprocess.Popen(command, cwd=root, start_new_session=True)
    children.append(backend)
    print(
        f"\nSEEK 寻物正在启动：{address}\n接口文档：{address}/docs\n按 Ctrl+C 同时停止本次启动的服务。\n",
        flush=True,
    )
    backend.wait()
except KeyboardInterrupt:
    print("\nStopping project services...", flush=True)
finally:
    for process in reversed(children):
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
