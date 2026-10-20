"""The cdx command: start, resume or inspect a quota-pool session."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
import argparse
import dataclasses
import json
import math
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from . import codex
from .pool import Pool
from .session import Lock, PoolError, Session, checked_id, read_json, write_json, normalize_usage

DEFAULT_HOMES = {"codex_main": ".codex", "codex_alt": ".codex-account-2",
                 "codex3": ".codex-account-3"}


NAME = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,47}\Z")


@dataclasses.dataclass(frozen=True)
class Config:
    accounts: tuple[str, ...]
    homes: dict[str, Path]
    threshold: float
    poll_seconds: float
    resume_when_available: bool
    binary: str
    sync_seconds: float = 5
    query_timeout: float = 30
    proxy_env: dict[str, str] = dataclasses.field(default_factory=dict)
    limit_ids: dict[str, str] = dataclasses.field(default_factory=dict)

    @classmethod
    def load(cls, path: Path):
        raw = read_json(path)
        if not isinstance(raw, dict):
            raise PoolError(f"配置文件不存在或不是 JSON 对象：{path}")
        known = {"accounts", "switch_below_percent", "poll_seconds", "resume_when_available",
                 "account_homes", "codex_binary", "sync_seconds", "query_timeout_seconds",
                 "proxy_env", "limit_ids"}
        if set(raw) - known:
            raise PoolError("未知配置项：" + ", ".join(sorted(set(raw) - known)))
        accounts = raw.get("accounts")
        if (not isinstance(accounts, list) or not accounts or
                any(not isinstance(x, str) or not NAME.fullmatch(x) for x in accounts) or
                len(set(accounts)) != len(accounts)):
            raise PoolError("accounts 必须是非空、无重复的账号名称数组")

        def number(key, default, lower, upper):
            n = raw.get(key, default)
            if isinstance(n, bool) or not isinstance(n, (int, float)) or not math.isfinite(n) or not lower <= n <= upper:
                raise PoolError(f"{key} 必须在 {lower}—{upper} 之间")
            return float(n)

        resume = raw.get("resume_when_available", False)
        if not isinstance(resume, bool):
            raise PoolError("resume_when_available 必须是 true 或 false")
        mappings = raw.get("account_homes", {})
        if not isinstance(mappings, dict) or any(not isinstance(v, str) for v in mappings.values()):
            raise PoolError("account_homes 必须是账号到目录的映射")
        homes = {}
        for account in accounts:
            home = mappings.get(account)
            if home is None:
                if account not in DEFAULT_HOMES:
                    raise PoolError(f"请在 account_homes 中配置 {account}")
                home = str(Path.home() / DEFAULT_HOMES[account])
            homes[account] = Path(home).expanduser().resolve()
        if len(set(homes.values())) != len(homes):
            raise PoolError("不同账号不能使用同一个 CODEX_HOME")
        binary = raw.get("codex_binary", shutil.which("codex") or "codex")
        if not isinstance(binary, str) or not shutil.which(binary):
            raise PoolError("找不到 codex_binary")
        proxy = raw.get("proxy_env", {})
        allowed = {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
                   "http_proxy", "https_proxy", "all_proxy", "no_proxy"}
        if not isinstance(proxy, dict) or set(proxy) - allowed or any(not isinstance(v, str) for v in proxy.values()):
            raise PoolError("proxy_env 只允许代理环境变量，值必须是字符串")
        limits = raw.get("limit_ids", {})
        if not isinstance(limits, dict) or any(not isinstance(v, str) or not v for v in limits.values()):
            raise PoolError("limit_ids 必须是账号到额度桶名称的映射")
        return cls(tuple(accounts), homes, number("switch_below_percent", 10, .1, 100),
                   number("poll_seconds", 15, 1, 3600), resume, str(Path(shutil.which(binary)).resolve()),
                   number("sync_seconds", 5, 1, 300), number("query_timeout_seconds", 30, 1, 120),
                   proxy, limits)

    def env(self, account: str):
        env = dict(os.environ)
        # These identify the invoking assistant, not the new supervised session.
        for key in ("OPENAI_API_KEY", "CODEX_API_KEY", "CODEX_THREAD_ID", "CODEX_TURN_ID"):
            env.pop(key, None)
        env.update(self.proxy_env)
        env["CODEX_HOME"] = str(self.homes[account])
        return env

LABELS = {"starting": "启动中", "running": "工作中", "idle": "等待输入", "draining": "使用剩余额度",
          "pausing": "正在暂停并同步", "paused_quota": "额度耗尽，已暂停", "paused_user": "已暂停",
          "paused_error": "异常暂停", "paused_query": "额度查询失败，已暂停",
          "quota_exhausted": "额度耗尽，正在交接"}

ROOT = Path(__file__).resolve().parent.parent


COMMANDS = {"run", "resume", "status"}


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="cdx", allow_abbrev=False,
        usage="cdx [OPTIONS] [PROMPT]\n       cdx resume [OPTIONS] [SESSION_ID] [PROMPT]\n       cdx status [--refresh] [--json]",
        description="直接进入原生 Codex，自动使用配置中的账号额度池。默认在当前目录开始新会话。",
        epilog="resume 默认选择当前项目的历史会话；--last 恢复最近一条，--all 跨项目选择。界面内 /fast、/plan 等由 Codex 处理。")
    p.add_argument("--pool-config", dest="config", type=Path, default=ROOT / "config.json", help="额度池配置文件")
    p.add_argument("--pool-runtime", dest="runtime", type=Path, default=ROOT / "runtime", help="额度池会话数据目录")
    p.add_argument("-C", "--cd", "--cwd", dest="cwd", type=Path, help="项目目录（默认当前目录；指定 ID 恢复时默认原目录）")
    p.add_argument("-m", "--model", help="使用指定模型")
    p.add_argument("-s", "--sandbox", choices=("read-only", "workspace-write", "danger-full-access"), help="Codex 沙箱模式")
    p.add_argument("-a", "--ask-for-approval", choices=("on-request", "never"), help="Codex 审批策略")
    p.add_argument("--add-dir", action="append", type=Path, default=[], help="额外可写目录，可重复")
    p.add_argument("--search", action="store_true", help="启用实时网页搜索")
    p.add_argument("--no-alt-screen", action="store_true", help="保留终端滚动历史")
    p.add_argument("--last", action="store_true", help="恢复最近的池内会话")
    p.add_argument("--all", action="store_true", help="恢复时包含其他项目的会话")
    p.add_argument("--prompt", dest="explicit_prompt", help="恢复后发送的消息，也可使用位置参数")
    p.add_argument("--refresh", action="store_true", help="status：实时查询额度")
    p.add_argument("--json", action="store_true", help="status：输出 JSON")
    p.add_argument("-V", "--version", action="store_true", help="显示底层 Codex 版本")
    args, words = p.parse_known_args(argv)
    # argparse leaves the end-of-options marker in unknown arguments. It also
    # lets a quoted task named "resume" be passed as `cdx -- resume`.
    literal_prompt = bool(words and words[0] == "--")
    before_marker = words[:words.index("--")] if "--" in words else words
    for word in before_marker:
        if word.startswith("-"):
            p.error(f"不支持的参数：{word}；使用 cdx --help 查看已支持参数")
    if "--" in words:
        words.remove("--")
    if words and words[0] in {"pause", "sync", "doctor", "check-config"} and not literal_prompt:
        p.error("精简版仅提供启动、resume 和 status；Ctrl+C 暂停，启动时自动检查和同步")
    args.command = words.pop(0) if words and words[0] in COMMANDS and not literal_prompt else "run"
    args.session, args.prompt = None, None
    if args.version:
        if words or args.command != "run":
            p.error("--version 不能与任务或子命令组合")
        args.command = "version"
    if args.command == "run":
        if len(words) > 1:
            p.error("任务请用引号包围，例如 cdx '修复测试失败'")
        args.prompt = words[0] if words else None
    elif args.command == "resume":
        if len(words) > 2:
            p.error("用法：cdx resume [SESSION_ID] [PROMPT]")
        if words:
            args.session = words[0]
        if len(words) == 2:
            args.prompt = words[1]
        if args.last and args.session:
            p.error("--last 不能与 SESSION_ID 同时使用")
    elif words:
        p.error("此子命令不接受位置参数")
    if args.explicit_prompt is not None:
        if args.prompt is not None:
            p.error("不能同时提供位置任务和 --prompt")
        args.prompt = args.explicit_prompt
    if args.command != "resume" and args.last:
        p.error("--last 仅用于 resume")
    if args.all and args.command not in ("resume", "status"):
        p.error("--all 仅用于 resume / status")
    if (args.refresh or args.json) and args.command != "status":
        p.error("--refresh / --json 仅用于 status")
    interactive_options = (args.cwd or args.model or args.sandbox or args.ask_for_approval or
                           args.add_dir or args.search or args.no_alt_screen or args.prompt is not None)
    if interactive_options and args.command not in ("run", "resume"):
        p.error("启动参数仅用于新会话或 resume")
    args.overrides = {}
    for value, key in ((args.model, "model"), (args.sandbox, "sandbox"), (args.ask_for_approval, "approvalPolicy")):
        if value is not None:
            args.overrides[key] = value
    if args.search:
        args.overrides.setdefault("config", {})["web_search"] = "live"
    if args.add_dir:
        args.overrides.setdefault("config", {})["sandbox_workspace_write"] = {"writable_roots": [
            str(path.expanduser().resolve()) for path in args.add_dir]}
    args.tui_options = ["--no-alt-screen"] if args.no_alt_screen else []
    return args


def select_resume(args):
    if args.session:
        return select_session(args.runtime, args.session)
    cwd = (args.cwd or Path.cwd()).expanduser().resolve()
    found = [s for s in sessions(args.runtime)
             if args.all or Path(s.state["cwd"]).resolve() == cwd]
    if not found:
        scope = "" if args.all else f"当前项目 {cwd} "
        raise PoolError(f"{scope}没有池内会话；运行 cdx 新建，或 cdx resume --all 跨项目查找")
    if args.last:
        return found[0]
    print("选择要恢复的额度池会话（最近的排在前面）：")
    for number, session in enumerate(found, 1):
        state = session.state
        stamp = datetime.fromtimestamp(state.get("updated_at", 0)).strftime("%m-%d %H:%M")
        print(f"  {number}. {stamp}  {state['id']}  {state['cwd']}")
    while True:
        try:
            answer = input("编号（回车选择 1，q 取消）：").strip()
        except EOFError:
            return None
        if answer.lower() in ("q", "quit"):
            return None
        if not answer:
            return found[0]
        if answer.isdecimal() and 1 <= int(answer) <= len(found):
            return found[int(answer) - 1]
        print("请输入列表中的编号，或 q 取消。")


def resume_hint(args, session, warnings=()):
    command = ["cdx"]
    if args.config != ROOT / "config.json":
        command += ["--pool-config", str(args.config)]
    if args.runtime != ROOT / "runtime":
        command += ["--pool-runtime", str(args.runtime)]
    command += ["resume", session.state["id"]]
    for warning in warnings:
        print(warning, file=sys.stderr)
    if session.state.get("pending_sync") or not session.state.get("last_sync_frozen"):
        print("保存同步尚未完成；恢复时将先核验并补齐同步。", file=sys.stderr)
    if session.state.get("status") == "paused_quota":
        print("额度已耗尽，任务已暂停。", file=sys.stderr)
    elif session.state.get("status") == "paused_query":
        print("暂时无法确认可用额度，任务已暂停。", file=sys.stderr)
    print("To reconnect, run:")
    print("  " + shlex.join(command), flush=True)
    usage = usage_line(session.state.get("token_usage"))
    if usage:
        print("\n" + usage, flush=True)


def usage_line(raw):
    usage = normalize_usage(raw)
    if not usage or not any(usage.values()):
        return None
    cached = usage["cached_input_tokens"]
    inputs = usage["input_tokens"] - cached
    outputs = usage["output_tokens"]
    line = f"Token usage so far: total={inputs + outputs:,} input={inputs:,}"
    if cached:
        line += f" (+ {cached:,} cached)"
    line += f" output={outputs:,}"
    if usage["reasoning_output_tokens"]:
        line += f" (reasoning {usage['reasoning_output_tokens']:,})"
    return line


def sessions(runtime):
    if not runtime.exists():
        return []
    result = []
    for path in runtime.glob("*/state.json"):
        result.append(Session(path.parent))
    return sorted(result, key=lambda s: s.state.get("updated_at", 0), reverse=True)


def select_session(runtime, ident=None):
    if ident:
        return Session(runtime / checked_id(ident))
    found = sessions(runtime)
    if not found:
        raise PoolError("还没有额度池会话；请先运行 cdx")
    return found[0]


def status(args, config):
    result = {"accounts": list(config.accounts), "switch_below_percent": config.threshold,
              "poll_seconds": config.poll_seconds, "resume_when_available": config.resume_when_available}
    cache_path = args.runtime / "quota-cache.json"
    failed = False
    if args.refresh:
        quotas, errors, _ = codex.query_all(config, args.runtime / "query")
        cache = {"queried_at": time.time(), "quotas": {n: dataclasses.asdict(q) for n, q in quotas.items()}, "errors": errors}
        write_json(cache_path, cache)
        failed = bool(errors)
    else:
        cache = read_json(cache_path, {"quotas": {}, "errors": {}})
    found = sessions(args.runtime)
    for session in found:
        for name, quota in session.state.get("quotas", {}).items():
            old = cache["quotas"].get(name, {})
            if quota.get("sampled_at", 0) > old.get("sampled_at", 0):
                cache["quotas"][name] = quota
    result.update(cache)
    result["sessions"] = []
    for session in found:
        s = session.state
        entry = {k: s.get(k) for k in ("id", "status", "active_account", "revision", "replicas", "last_sync_at",
                                       "last_sync_frozen", "pause_reason", "error", "sync_error")}
        entry["controller_running"] = codex.alive(s.get("controller"))
        entry["sync_pending"] = bool(s.get("pending_sync"))
        result["sessions"].append(entry)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(quota_table(config, cache))
        for s in result["sessions"]:
            state = LABELS.get(s["status"], s["status"])
            if not s["controller_running"] and s["status"] in ("running", "draining", "starting", "pausing"):
                state = "控制器未运行，需要 resume 核验恢复"
            print(f"\n会话 {s['id']}\n  {state}；当前账号 {s['active_account']}；检查点 v{s['revision']}")
            print("  " + "，".join(f"{n}: v{s['replicas'].get(n, {}).get('revision', '?')}" for n in config.accounts))
            if s["sync_pending"]:
                print("  同步未完成，旧副本禁止恢复；运行 cdx resume 修复")
            for key in ("error", "sync_error"):
                if s.get(key):
                    print(f"  {s[key]}")
    return 1 if failed else 0


def quota_table(config, cache):
    lines = ["账号  |  5h 剩余  |  周剩余  |  重置时间（5h / 周）"]
    for name in config.accounts:
        if name in cache.get("errors", {}):
            lines.append(f"{name}: {cache['errors'][name]}")
            continue
        windows = {w.get("window_minutes"): w for w in cache.get("quotas", {}).get(name, {}).get("windows", [])}
        cells, resets = [], []
        for minutes in (300, 10080):
            window = windows.get(minutes, {})
            value, stamp = window.get("remaining_percent"), window.get("resets_at")
            valid = type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 100
            cells.append(f"{value:g}%" if valid else "未知")
            try:
                resets.append(datetime.fromtimestamp(stamp).strftime("%m-%d %H:%M") if type(stamp) in (int, float) and stamp > 0 else "未知")
            except (ValueError, OSError, OverflowError):
                resets.append("未知")
        lines.append(f"{name}  |  {cells[0]}  |  {cells[1]}  |  {' / '.join(resets)}")
    lines.append(f"5h 切换阈值 {config.threshold:g}%；周额度为 0% 时停用。")
    return "\n".join(lines)


def main(argv=None):
    os.umask(0o077)
    args = parse_args(argv)
    args.config, args.runtime = args.config.expanduser().resolve(), args.runtime.expanduser().resolve()
    try:
        config = Config.load(args.config)
        if args.command == "version":
            return subprocess.call([config.binary, "--version"])
        codex.check_version(config)
        if args.command == "status":
            return status(args, config)
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            raise PoolError("启动和恢复需要交互式终端；请在普通终端运行 cdx")
        selected = select_resume(args) if args.command == "resume" else None
        if args.command == "resume" and selected is None:
            return 0
        with Lock(args.runtime / "pool.lock"):
            pool = Pool(config, args.runtime)
            pool.overrides, pool.tui_options = args.overrides, args.tui_options
            pool.cwd_override = args.cwd.expanduser().resolve() if args.cwd else None
            try:
                if selected:
                    pool.attach(selected)
                else:
                    pool.create(args.cwd or Path.cwd(), args.model)
                return pool.loop(args.prompt) or 0
            finally:
                try:
                    pool.close()
                finally:
                    if pool.session and pool.owns_session:
                        resume_hint(args, pool.session, pool.warnings)
    except KeyboardInterrupt:
        print("\n已取消。", file=sys.stderr)
        return 130
    except (PoolError, OSError, ValueError) as exc:
        print(f"额度池：{exc}", file=sys.stderr)
        return 1
