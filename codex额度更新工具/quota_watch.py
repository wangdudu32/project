#!/usr/bin/env python3
"""Local, multi-account Codex quota scheduler. Python standard library only."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import contextlib
import dataclasses
import datetime as dt
import fcntl
import hashlib
import json
import logging
import logging.handlers
import math
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import subprocess
import sys
import threading
import time
import unicodedata

ROOT = Path(__file__).resolve().parent
TZ = dt.timezone(dt.timedelta(hours=8), "Asia/Shanghai")
PROXY_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
              "http_proxy", "https_proxy", "all_proxy", "no_proxy")
NAME_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,47}\Z")
PROMPT = ("请用中文介绍一条 Python 编程技巧，附一个简短例子，总共约 200 字。"
          "直接回答即可，不使用工具，不读取文件，不执行命令，不联网。")


class WatchError(Exception):
    pass


class Cancelled(WatchError):
    pass


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except (ValueError, OSError) as exc:
        raise WatchError(f"无法读取 {path.name}；请检查文件，不能安全地忽略已有状态") from exc


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def formatted(ts):
    return dt.datetime.fromtimestamp(ts, TZ).strftime("%Y-%m-%d %H:%M:%S") if ts else "未知"


def formatted_duration(seconds):
    if seconds is None:
        return "未知"
    hours, remainder = divmod(max(0, int(seconds)), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}h {minutes}m {seconds}s"


def working(ts: float) -> bool:
    return 8 <= dt.datetime.fromtimestamp(ts, TZ).hour < 22


def next_work_time(ts: float) -> float:
    local = dt.datetime.fromtimestamp(ts, TZ)
    if local.hour < 8:
        return local.replace(hour=8, minute=0, second=0, microsecond=0).timestamp()
    if local.hour >= 22:
        return (local + dt.timedelta(days=1)).replace(
            hour=8, minute=0, second=0, microsecond=0).timestamp()
    return ts


def work_end(ts: float) -> float:
    return dt.datetime.fromtimestamp(ts, TZ).replace(
        hour=22, minute=0, second=0, microsecond=0).timestamp()


@dataclasses.dataclass
class Quota:
    used: float
    reset: float | None
    identity: str

    def as_dict(self):
        return {"remaining_percent": 100 - self.used, "resets_at": self.reset}


def parse_quota(result: dict, identity: str, limit_id="codex") -> Quota:
    buckets = result.get("rateLimitsByLimitId")
    if isinstance(buckets, dict) and buckets:
        bucket = buckets.get(limit_id)
    else:
        bucket = result.get("rateLimits")
        if isinstance(bucket, dict) and bucket.get("limitId") not in (None, limit_id):
            bucket = None
    if not isinstance(bucket, dict):
        raise WatchError(f"没有找到额度桶 {limit_id}，跳过任务")
    windows = [bucket.get(key) for key in ("primary", "secondary")]
    windows = [w for w in windows if isinstance(w, dict) and w.get("windowDurationMins") == 300]
    if len(windows) != 1:
        raise WatchError("无法唯一识别 300 分钟额度窗口，跳过任务")
    window = windows[0]
    used = window.get("usedPercent")
    if isinstance(used, bool) or not isinstance(used, (int, float)) or not math.isfinite(used) or not 0 <= used <= 100:
        raise WatchError("额度比例无效，跳过任务")
    reset = window.get("resetsAt")
    if reset is not None and (isinstance(reset, bool) or not isinstance(reset, (int, float))
                              or not math.isfinite(reset) or not 0 < reset < 253402214400):
        raise WatchError("刷新时间无效，跳过任务")
    return Quota(used, reset, identity)


def stop_process(proc):
    with contextlib.suppress(ProcessLookupError):
        os.killpg(proc.pid, signal.SIGTERM)
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=3)


class AppServer:
    """Short-lived stdio JSON-RPC connection; no credential handling here."""
    def __init__(self, command, env, cwd, timeout, cancelled):
        self.command, self.env, self.cwd = command, env, cwd
        self.timeout, self.cancelled = timeout, cancelled
        self.buffer = b""
        self.counter = 0

    def __enter__(self):
        self.deadline = time.monotonic() + self.timeout
        self.proc = subprocess.Popen(self.command, env=self.env, cwd=self.cwd,
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, start_new_session=True)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.proc.stdout, selectors.EVENT_READ)
        try:
            self.call("initialize", {"clientInfo": {"name": "codex_quota_watch", "version": "1.0.0"},
                                     "capabilities": {"experimentalApi": False}})
            self.send({"method": "initialized"})
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def send(self, obj):
        try:
            self.proc.stdin.write((json.dumps(obj) + "\n").encode())
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise WatchError("Codex app-server 连接已关闭") from exc

    def call(self, method, params=None):
        self.counter += 1
        request_id = self.counter
        request = {"id": request_id, "method": method}
        if params is not None:
            request["params"] = params
        self.send(request)
        while True:
            if self.cancelled.is_set():
                raise Cancelled("已停止")
            left = self.deadline - time.monotonic()
            if left <= 0:
                raise WatchError("额度查询超时（请检查代理和网络）")
            while b"\n" in self.buffer:
                line, self.buffer = self.buffer.split(b"\n", 1)
                try:
                    message = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(message, dict) or message.get("id") != request_id:
                    continue
                if "error" in message:
                    # Never put raw upstream error bodies or access tokens in logs.
                    code = message["error"].get("code", "unknown")
                    raise WatchError(f"Codex {method} 失败（RPC {code}，请检查代理、网络或登录状态）")
                if "result" not in message:
                    raise WatchError("Codex 返回了无效响应")
                return message["result"]
            if self.selector.select(min(left, 0.5)):
                data = os.read(self.proc.stdout.fileno(), 65536)
                if not data:
                    raise WatchError("Codex app-server 提前退出（请检查运行权限和配置）")
                self.buffer += data
                if len(self.buffer) > 4 * 1024 * 1024:
                    raise WatchError("Codex 响应过大")

    def __exit__(self, *args):
        self.selector.close()
        stop_process(self.proc)
        self.proc.stdin.close()
        self.proc.stdout.close()


class CodexGateway:
    def __init__(self, config, name, root, cancelled):
        self.config, self.name, self.root, self.cancelled = config, name, root, cancelled
        self.account = config["accounts"][name]
        self.work = root / "runtime" / name / "work"
        self.work.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.env = dict(os.environ)
        for key in PROXY_KEYS + ("OPENAI_API_KEY", "CODEX_API_KEY", "CODEX_THREAD_ID", "CODEX_TURN_ID"):
            self.env.pop(key, None)
        self.env.update(config.get("proxy_env", {}))
        self.env["CODEX_HOME"] = self.account["home"]

    def query(self, timeout) -> Quota:
        command = [self.config["codex_binary"], "app-server", "--listen", "stdio://"]
        with AppServer(command, self.env, self.work, timeout, self.cancelled) as server:
            result = server.call("account/read", {"refreshToken": False})
            account = result.get("account") or {}
            if account.get("type") not in ("chatgpt", "chatgptAuthTokens"):
                raise WatchError("该账号没有有效的 ChatGPT 登录，跳过任务")
            identifier = account.get("chatgptAccountId") or account.get("email")
            if not identifier:
                raise WatchError("无法确认账号身份，跳过任务")
            identity = hashlib.sha256(identifier.encode()).hexdigest()
            rates = server.call("account/rateLimits/read")
            return parse_quota(rates, identity, self.account.get("limit_id", "codex"))

    def task(self, timeout):
        outputs = self.root / "runtime" / self.name / "outputs"
        outputs.mkdir(exist_ok=True, mode=0o700)
        stamp = dt.datetime.now(TZ).strftime("%Y%m%d-%H%M%S-%f")
        target = outputs / (stamp + ".txt")
        command = [self.config["codex_binary"], "exec", "--ignore-user-config",
                   "--model", self.account["model"], "--sandbox", "read-only",
                   "--skip-git-repo-check", "--ephemeral", "--color", "never",
                   "-c", 'model_reasoning_effort="low"', "-c", 'web_search="disabled"',
                   "-c", "features.shell_tool=false", "-c", "features.apps=false",
                   "-c", "features.plugins=false", "-c", "features.hooks=false",
                   "-c", "features.multi_agent=false",
                   "--output-last-message", str(target), PROMPT]
        proc = subprocess.Popen(command, env=self.env, cwd=self.work, stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                start_new_session=True)
        deadline = time.monotonic() + timeout
        try:
            while proc.poll() is None:
                if self.cancelled.wait(0.25):
                    raise Cancelled("任务已停止，可能已经产生少量用量")
                if time.monotonic() >= deadline:
                    raise WatchError("小任务超时或到达休息时间，结果不确定；下轮先查询额度")
            if proc.returncode:
                raise WatchError(f"小任务退出码 {proc.returncode}，下轮先查询额度")
            return target.name
        finally:
            stop_process(proc)
            for old in sorted(outputs.glob("*.txt"))[:-30]:
                old.unlink()


class Runner:
    def __init__(self, root, name, config, gateway, cancelled, clock=time.time):
        self.root, self.name, self.config = root, name, config
        self.gateway, self.cancelled, self.clock = gateway, cancelled, clock
        self.path = root / "runtime" / name / "state.json"
        self.state = read_json(self.path, {})
        if not isinstance(self.state, dict):
            raise WatchError("状态文件格式错误，已停止，避免重复消耗")
        for key in ("next_check", "budget_until", "attempts", "consecutive_failures"):
            value = self.state.get(key, 0)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise WatchError(f"状态字段 {key} 无效，已停止，避免重复消耗")
        self.log = logging.getLogger("quota." + name)

    def save(self):
        self.state["updated_at"] = self.clock()
        write_json(self.path, self.state)

    def schedule(self, when, status):
        self.state.update(next_check=next_work_time(when), status=status, resume_status=status)
        self.save()

    def tick(self):
        now = self.clock()
        if not working(now):
            self.schedule(now, "休息中，等待 08:00")
            return
        # Persisted deadlines prevent stop/start from bypassing backoff or verification.
        due = self.state.get("next_check", 0)
        if now < due:
            return
        self.state["status"] = "查询额度"
        self.save()
        try:
            quota = self.gateway.query(min(self.config["query_timeout_seconds"], work_end(now) - now))
        except Cancelled:
            raise
        except (WatchError, OSError) as exc:
            self.failure(str(exc))
            return
        now = self.clock()
        previous_identity = self.state.get("identity")
        if previous_identity and previous_identity != quota.identity:
            self.state["status"] = "账号身份变化，已暂停；请核对账号目录后重新注册"
            self.save()
            raise WatchError("账号目录的登录身份发生变化；为避免误用已停止监测")
        self.state.update(identity=quota.identity, last_quota=quota.as_dict(),
                          last_success=now, consecutive_failures=0, last_error=None)
        self.log.info("额度剩余 %s%%；刷新时间 %s", 100 - quota.used, formatted(quota.reset))
        if not working(now):
            self.schedule(now, "休息中，等待 08:00")
            return
        # Only an elapsed window resets the attempt budget; moving reset timestamps
        # within a window cannot produce an unbounded series of model requests.
        if now >= self.state.get("budget_until", 0):
            self.state.update(attempts=0, budget_until=quota.reset if quota.reset and quota.reset > now else now + 18000)
        elif quota.reset and quota.reset > now:
            self.state["budget_until"] = quota.reset
        if quota.used > 0:
            self.state["inflight"] = False
            due = quota.reset + self.config["settle_seconds"] if quota.reset and quota.reset > now else now + self.config["retry_seconds"]
            self.schedule(due, "等待额度刷新" if quota.reset and quota.reset > now else "等待有效刷新时间")
            return
        if self.state.get("attempts", 0) >= self.config["max_attempts_per_window"]:
            due = max(self.state["budget_until"], now) + self.config["settle_seconds"]
            self.schedule(due, "已达本周期任务上限，等待下一周期")
            return
        if self.cancelled.is_set():
            raise Cancelled("已停止")
        # Save before launching so a crash never refunds an uncertain request.
        self.state.update(attempts=self.state.get("attempts", 0) + 1, inflight=True,
                          last_attempt=now, status="执行小任务",
                          next_check=next_work_time(now + self.config["settle_seconds"]))
        self.save()
        self.log.info("开始小任务，本周期第 %s/%s 次", self.state["attempts"], self.config["max_attempts_per_window"])
        try:
            result = self.gateway.task(min(self.config["task_timeout_seconds"], work_end(now) - now))
        except Cancelled:
            raise
        except (WatchError, OSError) as exc:
            self.failure(str(exc))
            return
        self.state.update(inflight=False, last_output=result)
        self.log.info("小任务完成，%s 秒后复查", self.config["settle_seconds"])
        self.schedule(self.clock() + self.config["settle_seconds"], "等待任务后复查")

    def failure(self, message):
        self.state["consecutive_failures"] = self.state.get("consecutive_failures", 0) + 1
        self.state["last_error"] = message
        self.log.warning("%s；第 %s 次失败，5 分钟后重试（夜间顺延到 08:00）",
                         message, self.state["consecutive_failures"])
        self.schedule(self.clock() + self.config["retry_seconds"], "异常，等待重试")

    def run(self):
        if self.state.get("status") in ("已停止", "已手动停止"):
            self.state["status"] = self.state.get("resume_status", "等待下次检查")
            self.save()
        while not self.cancelled.is_set():
            self.tick()
            self.cancelled.wait(min(30, max(0.1, self.state.get("next_check", self.clock()) - self.clock())))
        self.state["status"] = "已停止"
        self.save()


@contextlib.contextmanager
def exclusive(path):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise WatchError("该账号已有监测进程运行") from exc
        yield


def config_path(root):
    return root / "config.json"


def load_config(root):
    config = read_json(config_path(root))
    if not isinstance(config, dict):
        raise WatchError("尚未初始化，请先运行 init")
    for key in ("query_timeout_seconds", "task_timeout_seconds", "retry_seconds", "settle_seconds", "max_attempts_per_window"):
        value = config.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise WatchError(f"配置字段 {key} 必须是正整数")
    for name in config.get("accounts", {}):
        if not NAME_RE.fullmatch(name):
            raise WatchError("账号名称无效")
    return config


def initialize(root):
    if config_path(root).exists():
        raise WatchError("配置已经存在，保留原配置；使用 add 添加账号")
    codex = shutil.which("codex")
    if not codex:
        raise WatchError("找不到 codex 命令")
    write_json(config_path(root), {
        "codex_binary": codex,
        "proxy_env": {k: os.environ[k] for k in PROXY_KEYS if k in os.environ},
        "query_timeout_seconds": 30, "task_timeout_seconds": 120,
        "retry_seconds": 300, "settle_seconds": 60, "max_attempts_per_window": 3,
        "accounts": {},
    })
    print("已初始化；作息为北京时间 08:00—22:00。尚未启动监测。")


def unit_name(name):
    return f"codex-quota@{name}.service"


def systemctl(*args, capture=False, check=True, timeout=None):
    return subprocess.run(["systemctl", "--user", *args], check=check, text=True,
                          stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.PIPE if capture else None, timeout=timeout)


def select_accounts(config, args):
    names = list(config["accounts"]) if args.all else args.accounts
    if not names:
        raise WatchError("请指定账号名称，或使用 --all")
    for name in names:
        if name not in config["accounts"]:
            raise WatchError(f"未注册账号：{name}")
    return list(dict.fromkeys(names))


def service_file(root):
    def quoted(value):
        return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%") + '"'
    path = root / "systemd" / "codex-quota@.service"
    path.parent.mkdir(exist_ok=True)
    text = f"""[Unit]
Description=Codex quota monitor (%i)
StartLimitIntervalSec=600
StartLimitBurst=3

[Service]
Type=simple
WorkingDirectory={str(root).replace('%', '%%')}
ExecStart={quoted(sys.executable)} {quoted(ROOT / 'quota_watch.py')} --root {quoted(root)} run %i
Restart=on-failure
RestartSec=300
RestartPreventExitStatus=78
TimeoutStopSec=10
KillMode=control-group
UMask=0077
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
"""
    path.write_text(text)
    print(path)


def account_report(root, config, name, cached, cancelled):
    """Read a display snapshot; never write the scheduler's state or run tasks."""
    warnings = []
    try:
        state = read_json(root / "runtime" / name / "state.json", {})
        if not isinstance(state, dict):
            raise WatchError("后台状态文件格式无效")
    except (WatchError, OSError) as exc:
        state = {}
        warnings.append(str(exc))
    try:
        active = systemctl("is-active", unit_name(name), capture=True, check=False, timeout=5)
        mode = active.stdout.strip()
        if mode not in ("active", "inactive", "failed", "activating", "deactivating", "reloading"):
            mode = "unknown"
        if mode == "unknown":
            warnings.append("无法读取后台服务状态")
    except (OSError, subprocess.SubprocessError):
        mode = "unknown"
        warnings.append("无法读取后台服务状态")

    quota = state.get("last_quota") or {}
    sampled_at = state.get("last_success")
    if not isinstance(quota, dict) or not isinstance(quota.get("remaining_percent"), (int, float)):
        quota, sampled_at = {}, None
    source = "cache" if quota else "none"
    query_ok, queried_at, error = None, None, None
    if not cached:
        try:
            gateway = CodexGateway(config, name, root, cancelled)
            fresh = gateway.query(min(30, config["query_timeout_seconds"]))
            quota = fresh.as_dict()
            sampled_at = time.time()
            source, query_ok = "live", True
        except Cancelled:
            raise
        except (WatchError, OSError, ValueError, TypeError) as exc:
            error = str(exc)
            query_ok = False
        queried_at = time.time()
    now = time.time()
    reset = quota.get("resets_at")
    seconds = max(0, int(reset - now)) if reset else None
    if mode == "active":
        monitoring = "监测中" if working(now) else "休息中，等待 08:00"
    else:
        monitoring = {"inactive": "已停止", "failed": "异常退出", "activating": "正在启动",
                      "deactivating": "正在停止", "reloading": "正在重载"}.get(mode, "监测状态未知")
    return {
        "account": name, "monitoring_state": mode, "monitoring_status": monitoring,
        "remaining_percent": quota.get("remaining_percent"), "resets_at": reset,
        "reset_time": formatted(reset), "seconds_until_reset": seconds,
        "time_until_reset": formatted_duration(seconds), "source": source,
        "sampled_at": sampled_at, "sample_time": formatted(sampled_at),
        "queried_at": queried_at, "query_time": formatted(queried_at),
        "query_ok": query_ok, "error": error, "warnings": warnings,
        "cache_expired": bool(source == "cache" and reset and reset <= now),
        "next_check": state.get("next_check") if mode == "active" else None,
    }


def print_report(report):
    print(f"{report['account']} · {report['monitoring_status']}")
    if report["error"]:
        print("  实时查询失败，请检查代理、网络或登录状态。")
        print(f"  原因：{report['error']}")
    source = {"live": "实时", "cache": "缓存（非实时）", "none": "暂无数据"}[report["source"]]
    remaining = report["remaining_percent"]
    fields = [
        ("数据来源", source),
        ("5h 剩余额度", f"{remaining:g}%" if remaining is not None else "未知"),
        ("距离刷新", report["time_until_reset"]),
        ("刷新时间", report["reset_time"]),
        ("本次查询时间" if report["source"] == "live" else "缓存采样时间", report["sample_time"]),
        ("下次自动检查", formatted(report["next_check"]) if report["monitoring_state"] == "active"
         else "—（未运行）" if report["monitoring_state"] in ("inactive", "failed") else "未知"),
    ]
    for label, value in fields:
        width = sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in label)
        print(f"  {label}{' ' * (16 - width)}{value}")
    if report["cache_expired"]:
        print("  缓存中的刷新时间已过，请实时查询以确认当前额度。")
    for warning in report["warnings"]:
        print(f"  提示：{warning}")


@contextlib.contextmanager
def query_cancellation():
    cancelled = threading.Event()
    previous = {}
    try:
        for signum in (signal.SIGTERM, signal.SIGINT):
            previous[signum] = signal.signal(signum, lambda *_: cancelled.set())
        yield cancelled
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def status(root, config, names, *, cached=False, json_output=False, single=False):
    if not names:
        print("[]" if json_output else "尚未注册账号")
        return 0
    if not cached and not json_output and sys.stderr.isatty():
        print(f"正在实时查询 {len(names)} 个账号…", file=sys.stderr, flush=True)
    with query_cancellation() as cancelled:
        # Each account has its own bounded RPC request, so a failed account cannot
        # prevent other accounts from returning their results.
        with ThreadPoolExecutor(max_workers=min(8, len(names))) as executor:
            futures = [executor.submit(account_report, root, config, name, cached, cancelled) for name in names]
            reports = [future.result() for future in futures]
        if cancelled.is_set():
            raise Cancelled("查询已取消")
    if json_output:
        print(json.dumps(reports[0] if single else reports, ensure_ascii=False, indent=2, allow_nan=False))
    else:
        for index, report in enumerate(reports):
            if index:
                print()
            print_report(report)
    # Even with cached fallback, a failed live request is not a successful query.
    return 1 if any(report["query_ok"] is False for report in reports) else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Codex 多账号额度监测（北京时间 08:00—22:00）")
    parser.add_argument("--root", type=Path, default=ROOT, help="配置和状态目录")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="初始化配置，保存当前代理环境")
    add = sub.add_parser("add", help="注册账号，不启动")
    add.add_argument("name")
    add.add_argument("--home", required=True, type=Path)
    add.add_argument("--model", required=True)
    add.add_argument("--limit-id", default="codex")
    sub.add_parser("prepare-service", help="生成 systemd 模板，尚不安装")
    list_cmd = sub.add_parser("list", help="查看所有账号的本地缓存和监测状态")
    list_cmd.add_argument("--json", action="store_true", help="输出 JSON")
    for verb in ("start", "stop", "status"):
        cmd = sub.add_parser(verb)
        cmd.add_argument("accounts", nargs="*")
        cmd.add_argument("--all", action="store_true")
        if verb == "status":
            cmd.add_argument("--cached", action="store_true", help="仅查看本地缓存，不访问额度接口")
            cmd.add_argument("--json", action="store_true", help="输出 JSON")
    for verb in ("check", "run", "logs"):
        cmd = sub.add_parser(verb)
        cmd.add_argument("account")
        if verb == "logs":
            cmd.add_argument("--lines", type=int, default=30)
        elif verb == "check":
            cmd.add_argument("--json", action="store_true", help="输出 JSON（默认显示易读文本）")
    args = parser.parse_args(argv)
    root = args.root.expanduser().resolve()
    os.umask(0o077)
    if args.command == "init":
        initialize(root)
        return 0
    config = load_config(root)
    if args.command == "add":
        if not NAME_RE.fullmatch(args.name):
            raise WatchError("账号名只能包含小写字母、数字、下划线和连字符（最多 48 字符）")
        home = args.home.expanduser().resolve()
        if not home.is_dir():
            raise WatchError("账号目录不存在")
        with exclusive(root / "registry.lock"):
            config = load_config(root)
            if args.name in config["accounts"]:
                raise WatchError("账号名称已存在，未覆盖原配置")
            if any(Path(a["home"]).resolve() == home for a in config["accounts"].values()):
                raise WatchError("该账号目录已经注册，不能重复监测")
            config["accounts"][args.name] = {"home": str(home), "model": args.model, "limit_id": args.limit_id}
            write_json(config_path(root), config)
        print(f"已注册 {args.name}，尚未启动监测")
    elif args.command == "prepare-service":
        service_file(root)
    elif args.command == "list":
        return status(root, config, list(config["accounts"]), cached=True, json_output=args.json)
    elif args.command in ("start", "stop", "status"):
        if args.accounts and args.all:
            raise WatchError("账号名称与 --all 只能选择一种")
        names = select_accounts(config, args)
        if args.command == "status":
            return status(root, config, names, cached=args.cached, json_output=args.json)
        else:
            verb = "enable" if args.command == "start" else "disable"
            systemctl(verb, "--now", *[unit_name(n) for n in names])
            if args.command == "stop":
                for name in names:
                    path = root / "runtime" / name / "state.json"
                    with exclusive(path.parent / "runner.lock"):
                        state = read_json(path, {})
                        state["status"] = "已手动停止"
                        write_json(path, state)
            print(("已启动：" if args.command == "start" else "已停止：") + ", ".join(names))
    else:
        name = args.account
        if name not in config["accounts"]:
            raise WatchError(f"未注册账号：{name}")
        if args.command == "logs":
            path = root / "runtime" / name / "watch.log"
            print("\n".join(path.read_text().splitlines()[-max(1, args.lines):]) if path.exists() else "尚无日志")
            return 0
        if args.command == "check":
            return status(root, config, [name], json_output=args.json, single=True)
        cancelled = threading.Event()
        signal.signal(signal.SIGTERM, lambda *_: cancelled.set())
        signal.signal(signal.SIGINT, lambda *_: cancelled.set())
        gateway = CodexGateway(config, name, root, cancelled)
        runtime = root / "runtime" / name
        handler = logging.handlers.RotatingFileHandler(runtime / "watch.log", maxBytes=1048576, backupCount=3)
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        formatter.converter = lambda ts: dt.datetime.fromtimestamp(ts, TZ).timetuple()
        handler.setFormatter(formatter)
        logger = logging.getLogger("quota." + name)
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
        with exclusive(runtime / "runner.lock"):
            runner = Runner(root, name, config, gateway, cancelled)
            logger.info("监测启动；账号 %s；工作时间 08:00—22:00；网络重试间隔 300 秒", name)
            try:
                runner.run()
            except Cancelled:
                runner.state["status"] = "已停止"
                runner.save()
            finally:
                logger.info("监测进程退出")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Cancelled:
        sys.exit(0)
    except (WatchError, OSError, subprocess.SubprocessError) as error:
        print(f"错误：{error}", file=sys.stderr)
        sys.exit(78)
