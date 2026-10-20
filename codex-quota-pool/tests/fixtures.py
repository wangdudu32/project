"""Isolated account/model fixtures and the common native-terminal test driver."""
from __future__ import annotations
from pathlib import Path
from unittest.mock import patch
import contextlib
import fcntl
import http.server
import json
import os
import pty
import select
import signal
import sqlite3
import struct
import subprocess
import sys
import termios
import threading
import time
import uuid
from contextlib import contextmanager

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from quota_pool import codex
from quota_pool.cli import main
from quota_pool.pool import Pool

class Provider:
    def __init__(self):
        self.requests = []
        self.delay = 0
        self.error = None
        self.cached_tokens = 0
        self.reasoning_tokens = 0
        owner = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                body = json.dumps({"object": "list", "data": []}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                data = json.loads(body)
                owner.requests.append(data)
                if owner.error:
                    self.send_response(owner.error)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"error":{"type":"usage_limit_reached","code":"usage_limit_reached","message":"quota fixture"}}')
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                serial = len(owner.requests)
                rid, mid = f"resp_fixture_{serial}", f"msg_fixture_{serial}"
                text = f"CHECKPOINT_{serial}: 测试进度已保存。"
                item = {"id": mid, "type": "message", "role": "assistant", "status": "completed",
                        "content": [{"type": "output_text", "text": text, "annotations": []}], "phase": "final_answer"}

                def event(kind, **fields):
                    msg = {"type": kind, **fields}
                    self.wfile.write(("event: " + kind + "\ndata: " + json.dumps(msg) + "\n\n").encode())
                    self.wfile.flush()

                with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                    event("response.created", response={"id": rid, "status": "in_progress"})
                    event("response.output_item.added", output_index=0,
                          item={"id": mid, "type": "message", "role": "assistant", "status": "in_progress", "content": []})
                    time.sleep(owner.delay)
                    event("response.output_text.delta", item_id=mid, output_index=0, content_index=0, delta=text)
                    event("response.output_item.done", output_index=0, item=item)
                    event("response.completed", response={"id": rid, "status": "completed", "output": [item],
                          "usage": {"input_tokens": 10, "output_tokens": 10, "total_tokens": 20,
                                    "input_tokens_details": {"cached_tokens": owner.cached_tokens},
                                    "output_tokens_details": {"reasoning_tokens": owner.reasoning_tokens}}})

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def args(self):
        values = {"model_provider": '"pool_test"', "model_providers.pool_test.name": '"pool_test"',
                  "model_providers.pool_test.base_url": f'"http://127.0.0.1:{self.server.server_port}/v1"',
                  "model_providers.pool_test.wire_api": '"responses"',
                  "model_providers.pool_test.requires_openai_auth": "false",
                  "model_providers.pool_test.supports_websockets": "false",
                  "features.plugins": "false", "features.apps": "false", "features.hooks": "false"}
        return [part for k, v in values.items() for part in ("-c", f"{k}={v}")]

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def fixture(home, tid=None):
    tid = tid or str(uuid.uuid4())
    home.mkdir(exist_ok=True)
    path = home / "sessions" / f"rollout-{tid}.jsonl"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({"type": "session_meta", "payload": {"id": tid}}) + "\n")
    with contextlib.closing(sqlite3.connect(home / "state_5.sqlite")) as db, db:
        db.executescript('''
          CREATE TABLE IF NOT EXISTS _sqlx_migrations(version INTEGER PRIMARY KEY, checksum BLOB, success INTEGER);
          INSERT OR IGNORE INTO _sqlx_migrations VALUES (1, X'0123', 1);
          CREATE TABLE IF NOT EXISTS threads(id TEXT PRIMARY KEY,rollout_path TEXT,cli_version TEXT,cwd TEXT,project_id TEXT);
          CREATE TABLE IF NOT EXISTS thread_spawn_edges(parent_thread_id TEXT,child_thread_id TEXT PRIMARY KEY,status TEXT);
        ''')
        db.execute("INSERT INTO threads VALUES (?,?,?,?,?)", (tid, str(path), "0.163.0", str(home.parent), "source-project"))
    return tid


def advance(home, tid, text):
    path = home / "sessions" / f"rollout-{tid}.jsonl"
    with path.open("a") as f:
        f.write(json.dumps({"type": "response_item", "payload": {"type": "message", "role": "assistant", "text": text}}) + "\n")


def wait_for(predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.05)
    raise AssertionError("condition not reached")


class Terminal:
    def __init__(self, root, cwd, args):
        self.master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 35, 120, 0, 0))

        def setup():
            os.setsid()
            fcntl.ioctl(slave, termios.TIOCSCTTY, 0)

        self.proc = subprocess.Popen(
            [sys.executable, str(Path(__file__)), "terminal", str(root), *args],
            cwd=cwd, env=dict(os.environ, TERM="xterm-256color"),
            stdin=slave, stdout=slave, stderr=slave, preexec_fn=setup)
        os.close(slave)
        self.output = bytearray()

    def pump(self, seconds=.1):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if select.select([self.master], [], [], .05)[0]:
                try:
                    block = os.read(self.master, 65536)
                except OSError:
                    return
                if not block:
                    return
                self.output.extend(block)
                for query, reply in ((b"\x1b[6n", b"\x1b[1;1R"), (b"\x1b[c", b"\x1b[?1;2c"),
                                     (b"\x1b[?u", b"\x1b[?0u")):
                    if query in block:
                        os.write(self.master, reply)

    def until(self, predicate, timeout=25):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.pump()
            if predicate():
                return
            if self.proc.poll() is not None:
                break
        raise AssertionError(f"terminal failed ({self.proc.poll()}): {bytes(self.output[-7000:])!r}")

    def send(self, data):
        os.write(self.master, data)

    def exit(self):
        self.send(b"\x03")
        self.until(lambda: self.proc.poll() is not None)
        self.pump()

    def close(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=5)
        os.close(self.master)


class HeadlessPool(Pool):
    """Drive turns without a TUI when checking synchronization and settings."""
    def start_tui(self, prompt=None):
        if prompt:
            self.start_turn(prompt)

    def start_turn(self, prompt):
        state = self.session.state
        params = {"threadId": state["id"], "input": [{"type": "text", "text": prompt}],
                  "clientUserMessageId": f"pool-{time.time_ns()}"}
        if state["settings"].get("sandbox"):
            params["sandboxPolicy"] = state["settings"]["sandbox"]
        # Journal before the call. A lost response must never trigger a replay.
        state["pending_turn"] = {"message_id": params["clientUserMessageId"], "prompt": prompt, "at": time.time()}
        self.session.save()
        result = self.backend.rpc.call("turn/start", params)
        self.active_turn = result["turn"]["id"]
        state["pending_turn"] = None
        state["needs_review"] = False
        state["resume_pending"] = True
        state["status"] = "running"
        self.session.save()



@contextmanager
def fake_accounts(levels, extra_args=(), created=None, reads=None):
    """Mock the account boundary; keep the production selection path intact."""
    original = codex.Backend

    class AccountRpc(codex.Rpc):
        def __init__(self, command, env, cwd, **kwargs):
            super().__init__([*command, *extra_args], env, cwd, **kwargs)
            self.fixture_account = Path(env["CODEX_HOME"]).name

    def backend(config, name, cwd, directory, **kwargs):
        result = original(config, name, cwd, directory, extra_args=extra_args, **kwargs)
        result.rpc.fixture_account = name
        if created is not None:
            created.append(result)
        return result

    def account(rpc, **kwargs):
        return {"chatgptAccountId": rpc.fixture_account}, "identity-" + rpc.fixture_account

    def quota(config, name, rpc, info, **kwargs):
        if reads is not None:
            reads.append(name)
        value = levels()[name]
        return codex.Quota(value, [], value == 0)

    with patch.object(codex, "Backend", side_effect=backend), \
            patch.object(codex, "Rpc", AccountRpc), \
            patch.object(codex, "read_account", side_effect=account), \
            patch.object(codex, "read_quota", side_effect=quota):
        yield


def fake_account_server():
    home = Path(os.environ["CODEX_HOME"])
    settings = json.loads((home / "fixture.json").read_text())
    if settings.get("ignore_term"):
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    for line in sys.stdin:
        request = json.loads(line)
        if "id" not in request:
            continue
        method = request["method"]
        if method == settings.get("delay_method") or settings.get("delay_method") == "all":
            (home / "waiting.pid").write_text(str(os.getpid()))
            time.sleep(settings.get("delay", 30))
        if method == "account/read":
            result = {"account": {"type": "chatgpt", "chatgptAccountId": home.name}}
        elif method == "account/rateLimits/read":
            result = {"rateLimits": {
                "primary": {"usedPercent": 20, "windowDurationMins": 300},
                "secondary": {"usedPercent": 99, "windowDurationMins": 10080}}}
        else:
            result = {}
        print(json.dumps({"id": request["id"], "result": result}), flush=True)


def terminal_main(root, args):
    extra = json.loads((root / "provider.json").read_text())
    with fake_accounts(lambda: json.loads((root / "levels.json").read_text()), extra):
        return main(args)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "terminal":
        raise SystemExit(terminal_main(Path(sys.argv[2]), sys.argv[3:]))
    fake_account_server()
