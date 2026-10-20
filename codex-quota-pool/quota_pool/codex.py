"""Codex app-server transport, account quotas and process lifecycle."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import base64
import contextlib
import dataclasses
import hashlib
import json
import math
import os
import queue
import re
import secrets
import signal
import socket
import struct
import subprocess
import threading
import time
import copy
from .session import PoolError, SUPPORTED_VERSION, thread_ids

def rpc_error_hint(error):
    """Explain known failures without echoing untrusted bodies or credentials."""
    message = str(error.get("message", "")).lower()
    if any(part in message for part in ("permission denied", "read-only file system", "operation not permitted")):
        return "账号目录访问被权限或沙箱阻止，请在普通终端检查目录权限"
    if any(part in message for part in ("error sending request", "connection refused", "connection reset",
                                        "failed to connect", "timed out", "timeout", "dns", "proxy",
                                        "certificate", "network is unreachable", "tls")):
        return "账号服务连接失败，请检查网络及 config.json 的 proxy_env 代理配置"
    if any(part in message for part in ("refresh_token_reused", "refresh_token_expired", "refresh_token_invalid",
                                        "invalid_grant", "token has expired", "token has been revoked")):
        return "登录凭据已失效，请重新登录对应账号"
    status = re.search(r"\b(?:http(?: status)?|status(?: code)?)\s*[:=]?\s*([45]\d{2})\b", message)
    if status:
        code = status.group(1)
        if code == "401":
            return "账号服务拒绝登录凭据（HTTP 401），请检查对应账号的登录状态"
        if code == "403":
            return "账号服务拒绝访问（HTTP 403），请检查账号权限和网络"
        if code == "429":
            return "账号服务限流（HTTP 429），请稍后重试"
        return f"账号服务返回 HTTP {code}，请稍后重试并检查网络"
    if error.get("code") == -32603:
        return "Codex 后端内部错误，请检查账号登录状态和网络代理"
    return None


class RpcError(PoolError):
    def __init__(self, method, error):
        self.method, self.error = method, error
        # Upstream bodies can contain credentials. Never print them verbatim.
        hint = rpc_error_hint(error)
        super().__init__(f"Codex {method} 失败（RPC {error.get('code', 'unknown')}）" +
                         (f"：{hint}" if hint else ""))


class QueryCancelled(PoolError):
    """A read-only query was cancelled by its owner."""


def stop_process(proc, timeout=5):
    if proc is None or proc.poll() is not None:
        return
    with contextlib.suppress(ProcessLookupError):
        os.killpg(proc.pid, signal.SIGTERM)
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=5)


class Rpc:
    """Concurrent JSONL requests; notifications are never discarded by a call."""
    def __init__(self, command, env, cwd, timeout=30, stderr=None, experimental=False,
                 cancel_event=None, deadline=None, close_timeout=5):
        self.cancel_event, self.deadline = cancel_event, deadline
        self.close_timeout = close_timeout
        self.proc = subprocess.Popen(command, env=env, cwd=cwd, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=stderr or subprocess.DEVNULL,
                                     start_new_session=True)
        self.timeout = timeout
        self.notifications = queue.Queue()
        self.pending = {}
        self.lock = threading.Lock()
        self.counter = 0
        self.closed = False
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()
        try:
            self.call("initialize", {"clientInfo": {"name": "codex_quota_pool", "version": "0.1.0"},
                                     "capabilities": {"experimentalApi": experimental}})
            self.send({"method": "initialized"})
        except BaseException:
            self.close()
            raise

    def send(self, message):
        with self.lock:
            try:
                self.proc.stdin.write(json.dumps(message).encode() + b"\n")
                self.proc.stdin.flush()
            except (OSError, ValueError) as exc:
                raise PoolError("Codex 连接已关闭") from exc

    def _read(self):
        try:
            for line in self.proc.stdout:
                try:
                    msg = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(msg, dict):
                    continue
                with self.lock:
                    target = self.pending.get(msg.get("id")) if "method" not in msg else None
                if target:
                    target.put(msg)
                elif "method" in msg:
                    self.notifications.put(msg)
        finally:
            self.closed = True
            with self.lock:
                for target in self.pending.values():
                    target.put(None)

    def call(self, method, params=None, timeout=None, *, cancel_event=None, deadline=None):
        cancel_event = cancel_event if cancel_event is not None else self.cancel_event
        deadline = deadline if deadline is not None else self.deadline
        end = time.monotonic() + (self.timeout if timeout is None else timeout)
        if deadline is not None:
            end = min(end, deadline)
        if cancel_event is not None and cancel_event.is_set():
            raise QueryCancelled("额度查询已取消")
        if time.monotonic() >= end:
            raise PoolError(f"Codex {method} 超时")
        target = queue.Queue()
        with self.lock:
            self.counter += 1
            ident = self.counter
            self.pending[ident] = target
        try:
            request = {"id": ident, "method": method}
            if params is not None:
                request["params"] = params
            self.send(request)
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    raise QueryCancelled("额度查询已取消")
                remaining = end - time.monotonic()
                if remaining <= 0:
                    raise PoolError(f"Codex {method} 超时")
                try:
                    result = target.get(timeout=min(remaining, .05) if cancel_event is not None else remaining)
                    break
                except queue.Empty:
                    continue
            if result is None:
                raise PoolError(f"Codex 在 {method} 时关闭连接")
            if "error" in result:
                raise RpcError(method, result["error"])
            if "result" not in result:
                raise PoolError(f"Codex {method} 返回无效响应")
            return result["result"]
        finally:
            with self.lock:
                self.pending.pop(ident, None)

    def drain(self):
        while True:
            try:
                yield self.notifications.get_nowait()
            except queue.Empty:
                return

    def close(self):
        stop_process(self.proc, timeout=self.close_timeout)
        self.reader.join(timeout=2)
        for stream in (self.proc.stdin, self.proc.stdout):
            with contextlib.suppress(OSError):
                stream.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class Backend:
    def __init__(self, config, account, cwd, directory, extra_args=(), *, cancel_event=None, deadline=None):
        self.config, self.account = config, account
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Authenticated localhost transport also works with long project paths.
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            self.port = reservation.getsockname()[1]
        self.address = f"ws://127.0.0.1:{self.port}"
        self.token = secrets.token_urlsafe(32)
        from .session import atomic_write
        self.token_path = self.directory / "backend.token"
        atomic_write(self.token_path, self.token.encode())
        self.log = (self.directory / "backend.log").open("ab", buffering=0)
        env = config.env(account)
        self.proc = subprocess.Popen([config.binary, "app-server", "--listen", self.address,
                                      "--ws-auth", "capability-token", "--ws-token-file", str(self.token_path),
                                      *extra_args], env=env, cwd=cwd, stdin=subprocess.DEVNULL,
                                     stdout=subprocess.DEVNULL, stderr=self.log, start_new_session=True)
        self.rpc = None
        try:
            deadline = deadline if deadline is not None else time.monotonic() + config.query_timeout
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    raise QueryCancelled("额度查询已取消")
                if self.proc.poll() is not None or time.monotonic() > deadline:
                    raise PoolError("Codex 后端启动失败；请查看 runtime 中的 backend.log")
                try:
                    self.rpc = WebSocketRpc(self.port, self.token, min(config.query_timeout, max(.01, deadline - time.monotonic())),
                                            cancel_event=cancel_event, deadline=deadline)
                    self.rpc.timeout = config.query_timeout
                    break
                except (ConnectionError, OSError):
                    time.sleep(.05)
        except BaseException:
            self.close(timeout=.2)
            raise

    def close(self, timeout=5):
        if self.rpc:
            self.rpc.close()
        stop_process(self.proc, timeout=timeout)
        self.log.close()
        with contextlib.suppress(FileNotFoundError):
            self.token_path.unlink()


class WebSocketRpc(Rpc):
    """Small RFC 6455 localhost client, including masking, ping and fragmentation."""
    def __init__(self, port, token, timeout=30, *, cancel_event=None, deadline=None):
        self.cancel_event = self.deadline = None
        self.socket = socket.create_connection(("127.0.0.1", port), timeout=timeout)
        self.timeout = timeout
        self.pending, self.counter = {}, 0
        self.lock = threading.Lock()
        self.send_lock = threading.Lock()
        self.notifications = queue.Queue()
        self.closed = False
        try:
            key = base64.b64encode(secrets.token_bytes(16)).decode()
            request = (f"GET / HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nUpgrade: websocket\r\n"
                       f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
                       f"Authorization: Bearer {token}\r\n\r\n")
            self.socket.sendall(request.encode())
            self.stream = self.socket.makefile("rb")
            status = self.stream.readline(8192)
            headers = {}
            for _ in range(100):
                line = self.stream.readline(8192)
                if line == b"\r\n":
                    break
                if not line or b":" not in line:
                    raise PoolError("Codex WebSocket 握手失败")
                k, v = line.split(b":", 1)
                headers[k.lower()] = v.strip()
            accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest())
            if b" 101 " not in status or headers.get(b"sec-websocket-accept") != accept:
                raise PoolError("Codex WebSocket 认证或握手失败")
            self.socket.settimeout(None)
            self.reader = threading.Thread(target=self._read_ws, daemon=True)
            self.reader.start()
            self.call("initialize", {"clientInfo": {"name": "codex_quota_pool", "version": "0.1.0"},
                                     "capabilities": {"experimentalApi": True}},
                      cancel_event=cancel_event, deadline=deadline)
            self.send({"method": "initialized"})
        except BaseException:
            with contextlib.suppress(OSError):
                self.socket.shutdown(socket.SHUT_RDWR)
            if hasattr(self, "reader"):
                self.reader.join(timeout=2)
            self.socket.close()
            if hasattr(self, "stream"):
                self.stream.close()
            raise

    def _frame(self, payload, opcode=1):
        mask = secrets.token_bytes(4)
        n = len(payload)
        length = bytes([n | 128]) if n < 126 else (b"\xfe" + struct.pack("!H", n) if n < 65536 else b"\xff" + struct.pack("!Q", n))
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        with self.send_lock:
            self.socket.sendall(bytes([128 | opcode]) + length + mask + masked)

    def send(self, message):
        try:
            self._frame(json.dumps(message).encode())
        except OSError as exc:
            raise PoolError("Codex WebSocket 连接已关闭") from exc

    def _exact(self, n):
        data = self.stream.read(n)
        if len(data) != n:
            raise EOFError
        return data

    def _read_ws(self):
        fragments = bytearray()
        try:
            while True:
                a, b = self._exact(2)
                opcode, size = a & 15, b & 127
                if size == 126:
                    size = struct.unpack("!H", self._exact(2))[0]
                elif size == 127:
                    size = struct.unpack("!Q", self._exact(8))[0]
                if b & 128 or size + len(fragments) > 64 * 1024 * 1024:
                    raise PoolError("WebSocket 帧无效或过大")
                payload = self._exact(size)
                if opcode == 8:
                    return
                if opcode == 9:
                    self._frame(payload, 10)
                    continue
                if opcode == 10:
                    continue
                if opcode not in (0, 1):
                    raise PoolError("不支持的 WebSocket 帧")
                fragments.extend(payload)
                if not a & 128:
                    continue
                msg = json.loads(fragments)
                fragments.clear()
                with self.lock:
                    target = self.pending.get(msg.get("id")) if "method" not in msg else None
                if target:
                    target.put(msg)
                elif "method" in msg:
                    self.notifications.put(msg)
        except (OSError, ValueError, EOFError, PoolError):
            pass
        finally:
            self.closed = True
            with self.lock:
                for target in self.pending.values():
                    target.put(None)

    def close(self):
        with contextlib.suppress(OSError):
            self.socket.shutdown(socket.SHUT_RDWR)
        self.reader.join(timeout=2)
        self.stream.close()
        self.socket.close()


def check_version(config):
    result = subprocess.run([config.binary, "--version"], capture_output=True, text=True, timeout=10)
    version = result.stdout.strip().split()[-1] if result.returncode == 0 and result.stdout.strip() else "unknown"
    if version != SUPPORTED_VERSION:
        raise PoolError(f"当前 Codex {version}；会话迁移仅验证了 {SUPPORTED_VERSION}，请先适配再运行")
    return version


def read_account(rpc, **call_options):
    account = rpc.call("account/read", {"refreshToken": False}, **call_options).get("account") or {}
    if account.get("type") not in ("chatgpt", "chatgptAuthTokens"):
        raise PoolError("账号未登录 ChatGPT")
    identifier = account.get("chatgptAccountId") or account.get("email")
    if not identifier:
        raise PoolError("无法确认账号身份")
    return account, hashlib.sha256(identifier.encode()).hexdigest()


def read_quota(config, name, rpc, account, **call_options):
    result = rpc.call("account/rateLimits/read", **call_options)
    actual = account.get("chatgptAccountId")
    if actual and result.get("accountId") not in (None, actual):
        raise PoolError("额度响应与登录账号不匹配")
    return Quota.parse(result, config.limit_ids.get(name, "codex"))


def query_account(config, name, work, cancel_event=None, rpc=None):
    if cancel_event is not None and cancel_event.is_set():
        raise QueryCancelled("额度查询已取消")
    if not config.homes[name].is_dir():
        raise PoolError(f"账号目录不存在：{config.homes[name]}")
    deadline = time.monotonic() + config.query_timeout
    options = {"cancel_event": cancel_event, "deadline": deadline}
    if rpc is not None:
        # Borrow the running session's transport, never close it on cancellation.
        account, identity = read_account(rpc, **options)
        return read_quota(config, name, rpc, account, **options), identity
    with Rpc([config.binary, "app-server", "--listen", "stdio://"], config.env(name), work,
             timeout=config.query_timeout, close_timeout=.2, **options) as rpc:
        account, identity = read_account(rpc)
        return read_quota(config, name, rpc, account), identity


def query_all(config, work, *, cancel_event=None, active=None):
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True, mode=0o700)
    quotas, errors, identities, results = {}, {}, {}, {}
    cancel_event = cancel_event if cancel_event is not None else threading.Event()
    executor = ThreadPoolExecutor(max_workers=min(len(config.accounts), 8))
    try:
        tasks = {executor.submit(query_account, config, name, work, cancel_event,
                                 active[1] if active and active[0] == name else None): name
                 for name in config.accounts}
        for task in as_completed(tasks):
            name = tasks[task]
            try:
                results[name] = task.result()
            except (PoolError, OSError, subprocess.SubprocessError) as exc:
                errors[name] = str(exc)
    except BaseException:
        cancel_event.set()
        raise
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
    # A duplicate alias must never displace the account that owns the session.
    order = sorted(config.accounts, key=lambda name: 0 if active and name == active[0] else 1)
    for name in order:
        if name not in results:
            continue
        quota, identity = results[name]
        if identity in identities.values():
            errors[name] = "与池内另一名称使用了相同的登录账号"
        else:
            quotas[name], identities[name] = quota, identity
    return quotas, errors, identities


def verify_model(rpc, settings, **call_options):
    model = settings.get("model")
    if not model:
        return
    cursor = None
    while True:
        params = {"includeHidden": True}
        if cursor:
            params["cursor"] = cursor
        result = rpc.call("model/list", params, **call_options)
        for entry in result.get("data", []):
            if model in (entry.get("id"), entry.get("model")):
                effort = settings.get("reasoningEffort")
                efforts = {e.get("reasoningEffort") for e in entry.get("supportedReasoningEfforts", [])}
                if effort and efforts and effort not in efforts:
                    raise PoolError(f"目标账号模型不支持原推理强度 {effort}")
                return
        cursor = result.get("nextCursor")
        if not cursor:
            raise PoolError(f"目标账号模型目录中没有 {model}；未自动降级")


@dataclasses.dataclass
class Quota:
    remaining: float
    windows: list[dict]
    exhausted: bool
    sampled_at: float = dataclasses.field(default_factory=time.time)

    def available(self, threshold: float):
        return not self.exhausted and self.remaining >= threshold

    @classmethod
    def parse(cls, response, limit_id="codex"):
        buckets = response.get("rateLimitsByLimitId")
        bucket = buckets.get(limit_id) if isinstance(buckets, dict) and buckets else response.get("rateLimits")
        if not isinstance(bucket, dict) or bucket.get("limitId") not in (None, limit_id):
            raise PoolError(f"额度桶 {limit_id} 不可用")
        windows = []
        for key in ("primary", "secondary"):
            w = bucket.get(key)
            if w is None:
                continue
            if not isinstance(w, dict):
                raise PoolError("额度窗口格式错误")
            used = w.get("usedPercent")
            if isinstance(used, bool) or not isinstance(used, (int, float)) or not math.isfinite(used) or not 0 <= used <= 100:
                raise PoolError("额度百分比无效")
            windows.append({"kind": key, "remaining_percent": 100 - used,
                            "window_minutes": w.get("windowDurationMins"), "resets_at": w.get("resetsAt")})
        if not windows:
            raise PoolError("服务端没有返回可判断的额度窗口")
        # Window positions are not a contract: identify 5h/week by duration.
        known = {}
        for window in windows:
            minutes = window["window_minutes"]
            if minutes in (300, 10080):
                if minutes in known:
                    raise PoolError("服务端返回重复的额度窗口")
                known[minutes] = window["remaining_percent"]
        exhausted = (any(value <= 0 for value in known.values()) or bool(bucket.get("rateLimitReachedType")) or
                     bucket.get("spendControlReached") is True or response.get("ordinaryUsageAllowed") is False)
        if not exhausted and (300 not in known or 10080 not in known):
            raise PoolError("缺少可识别的 5h 或周额度窗口，额度未知")
        # Weekly quota is only a hard stop at zero; the threshold applies to 5h.
        remaining = known.get(300, 0)
        return cls(remaining, windows, exhausted)


def next_account(order, active, quotas, threshold):
    """Quota errors are absent, never converted to zero or cached eligibility."""
    order = list(order)
    if active in order:
        i = order.index(active)
        order = order[i + 1:] + order[:i]
    for name in order:
        if name != active and name in quotas and quotas[name].available(threshold):
            return name
    return None


def decision(active, order, quotas, threshold):
    current = quotas.get(active)
    if current is None:
        return "unknown", None
    if current.available(threshold) and active in order:
        return "continue", None
    target = next_account(order, active, quotas, threshold)
    if target:
        return "switch", target
    if current.exhausted or active not in order:
        return "pause", None
    return "drain", None


def process_stamp(pid):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(") ", 1)[1].split()
        return None if fields[0] == "Z" else fields[19]
    except (FileNotFoundError, ProcessLookupError, IndexError):
        return None


def process_record(pid):
    return {"pid": pid, "stamp": process_stamp(pid)}


def alive(record):
    return bool(record and record.get("stamp") and process_stamp(record["pid"]) == record["stamp"])


def terminate_record(record, group=False):
    if not alive(record):
        return
    pid = record["pid"]
    if group and os.getpgid(pid) != pid:
        raise PoolError("记录的 Codex 后端进程组不匹配，拒绝误杀其他进程")
    (os.killpg if group else os.kill)(pid, signal.SIGTERM)
    deadline = time.monotonic() + 5
    while alive(record) and time.monotonic() < deadline:
        time.sleep(.05)
    if alive(record):
        (os.killpg if group else os.kill)(pid, signal.SIGKILL)


def saved_settings(result):
    return {key: result[key] for key in ("model", "modelProvider", "reasoningEffort", "approvalPolicy",
                                        "approvalsReviewer", "sandbox", "serviceTier", "collaborationMode",
                                        "disabledPluginIds") if key in result}


def merge_config(base, overrides):
    result = copy.deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_config(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def resume_params(state):
    s = state["settings"]
    params = {"threadId": state["id"], "excludeTurns": True, "cwd": state["cwd"],
              "config": copy.deepcopy(state.get("launch_config", {}))}
    for key in ("model", "modelProvider", "approvalPolicy", "approvalsReviewer", "serviceTier"):
        if s.get(key) is not None:
            params[key] = s[key]
    if s.get("reasoningEffort"):
        params["config"]["model_reasoning_effort"] = s["reasoningEffort"]
    sandbox = s.get("sandbox", {}).get("type")
    if sandbox in ("readOnly", "workspaceWrite", "dangerFullAccess"):
        params["sandbox"] = {"readOnly": "read-only", "workspaceWrite": "workspace-write",
                             "dangerFullAccess": "danger-full-access"}[sandbox]
    if sandbox == "workspaceWrite":
        policy = s["sandbox"]
        params.setdefault("config", {})["sandbox_workspace_write"] = {
            "writable_roots": policy.get("writableRoots", []),
            "network_access": policy.get("networkAccess", False),
            "exclude_tmpdir_env_var": policy.get("excludeTmpdirEnvVar", False),
            "exclude_slash_tmp": policy.get("excludeSlashTmp", False),
        }
    return params


def verify_permissions(expected, actual):
    for key in ("approvalPolicy", "approvalsReviewer", "sandbox"):
        if expected.get(key) != actual.get(key):
            raise PoolError(f"目标账号无法保留原会话的 {key}，已暂停；请统一账号权限配置后恢复")


def interrupt_tree(rpc, home, root_id, timeout=30):
    """Quiesce all descendants and goals before closing our private backend."""
    deadline = time.monotonic() + timeout
    paused_goals = []
    interrupted = set()
    while time.monotonic() < deadline:
        busy = False
        ids = thread_ids(home, root_id)
        if root_id not in ids:
            ids.insert(0, root_id)
        for tid in ids:
            goal = rpc.call("thread/goal/get", {"threadId": tid}).get("goal")
            if goal and goal.get("status") == "active":
                # The user explicitly authorized threshold/stop pauses in this pool.
                rpc.call("thread/goal/set", {"threadId": tid, "status": "paused", "origin": "user"})
                paused_goals.append(tid)
            info = rpc.call("thread/read", {"threadId": tid})["thread"]
            if info.get("status", {}).get("type") == "active":
                busy = True
                turns = rpc.call("thread/turns/list", {"threadId": tid, "limit": 1, "sortDirection": "desc"}).get("data", [])
                if not turns:
                    raise PoolError("活动任务没有可确认的轮次，停止自动切换")
                rpc.call("turn/interrupt", {"threadId": tid, "turnId": turns[0]["id"]})
                interrupted.add(tid)
        if not busy:
            return paused_goals, interrupted
        time.sleep(.1)
    raise PoolError("任务中断未确认，已停止交接；不会启动另一个账号")
