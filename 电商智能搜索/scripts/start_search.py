"""Run from the project root: python scripts/start_search.py [--download-only|--stop]."""

import argparse
import hashlib
import json
import os
import platform
import signal
import subprocess
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path


parser = argparse.ArgumentParser(
    description="Download and run a project-local OpenSearch node"
)
parser.add_argument("--download-only", action="store_true")
parser.add_argument("--stop", action="store_true")
arguments = parser.parse_args()
root = Path.cwd().resolve()
runtime = root / "runtime"
runtime.mkdir(exist_ok=True)
version = "3.9.0"
architecture = "arm64" if platform.machine() in ("arm64", "aarch64") else "x64"
service_root = runtime / "services"
service_root.mkdir(exist_ok=True)
home = service_root / f"opensearch-{version}"
pid_file = runtime / "opensearch.pid"

if arguments.stop:
    if not pid_file.exists():
        print("No project-owned OpenSearch PID file.")
    else:
        pid = int(pid_file.read_text())
        process = Path(f"/proc/{pid}/cmdline")
        if process.exists() and str(home).encode() in process.read_bytes():
            os.kill(pid, signal.SIGTERM)
            print("Stopped project OpenSearch.")
        else:
            print("The recorded process no longer belongs to this OpenSearch instance.")
        pid_file.unlink(missing_ok=True)
    raise SystemExit(0)

if not (home / "bin" / "opensearch").exists():
    archive = service_root / f"opensearch-{version}-linux-{architecture}.tar.gz"
    url = f"https://artifacts.opensearch.org/releases/bundle/opensearch/{version}/{archive.name}"
    partial = archive.with_suffix(".part")
    print("Downloading official OpenSearch distribution (about 1 GB)...", flush=True)
    if not archive.exists():
        with (
            urllib.request.urlopen(url, timeout=90) as response,
            partial.open("wb") as output,
        ):
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        partial.replace(archive)
    with urllib.request.urlopen(url + ".sha512", timeout=30) as response:
        expected = response.read().decode().split()[0].lower()
    checksum = hashlib.sha512()
    with archive.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            checksum.update(chunk)
    if checksum.hexdigest() != expected:
        raise SystemExit(
            "Checksum mismatch. Remove the downloaded archive before retrying."
        )
    print("Checksum verified. Extracting...", flush=True)
    with tarfile.open(archive) as source:
        source.extractall(service_root, filter="data")

if arguments.download_only:
    print(f"OpenSearch ready at {home}")
    raise SystemExit(0)

url = "http://127.0.0.1:9200"
try:
    with urllib.request.urlopen(url, timeout=2) as response:
        info = json.load(response)
    if info.get("version", {}).get("distribution") != "opensearch":
        raise SystemExit("Port 9200 is occupied by another service.")
    print("An OpenSearch node is already available on 127.0.0.1:9200.")
    raise SystemExit(0)
except (urllib.error.URLError, TimeoutError):
    pass

configuration = f"""cluster.name: seek-local
node.name: seek-node
network.host: 127.0.0.1
http.port: 9200
discovery.type: single-node
plugins.security.disabled: true
path.data: {runtime / "opensearch-data"}
path.logs: {runtime / "opensearch-logs"}
"""
(home / "config" / "opensearch.yml").write_text(configuration)
environment = {
    **os.environ,
    "OPENSEARCH_JAVA_OPTS": "-Xms512m -Xmx512m",
    "DISABLE_INSTALL_DEMO_CONFIG": "true",
}
with (runtime / "opensearch-console.log").open("a") as output:
    process = subprocess.Popen(
        [str(home / "bin" / "opensearch")],
        cwd=home,
        env=environment,
        stdout=output,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
pid_file.write_text(str(process.pid))
for attempt in range(60):
    if process.poll() is not None:
        raise SystemExit("OpenSearch exited. Read runtime/opensearch-console.log.")
    try:
        with urllib.request.urlopen(url, timeout=1) as response:
            info = json.load(response)
        print(f"OpenSearch {info['version']['number']} is ready at {url}")
        break
    except (urllib.error.URLError, TimeoutError):
        time.sleep(0.5)
else:
    raise SystemExit(
        "Startup is still in progress. Check runtime/opensearch-console.log."
    )

print(
    "Keep this terminal open. Press Ctrl+C to stop the project search node.", flush=True
)


def stop_requested(signum, frame):
    raise KeyboardInterrupt


signal.signal(signal.SIGTERM, stop_requested)
try:
    process.wait()
except KeyboardInterrupt:
    process.terminate()
    process.wait(timeout=30)
finally:
    pid_file.unlink(missing_ok=True)
