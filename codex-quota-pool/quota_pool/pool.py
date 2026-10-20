"""Start, monitor, hand off and stop one quota-pool session."""
from __future__ import annotations
import contextlib
import copy
from concurrent.futures import ThreadPoolExecutor
import dataclasses
from functools import wraps
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from . import codex
from .session import Lock, PoolError, Session, Syncer, check_home_layout, checkpoint_usage, normalize_usage
from .terminal import TerminalRelay

CONTINUE = ("上一轮由本地额度池暂停或因账号额度耗尽中断，现在已恢复到最新检查点。"
            "请继续用户原来的未完成任务。先核验中断前的命令、文件修改和外部操作是否已完成，"
            "避免重复执行；保留尚未获得的用户确认。如果原任务已经完成，直接说明完成状态。")


def timed(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        start = time.monotonic()
        try:
            return method(self, *args, **kwargs)
        finally:
            self._record_timing(method.__name__, start)
    return wrapped


class Pool:
    def __init__(self, config, runtime: Path):
        self.config, self.runtime = config, runtime
        self.session = None
        self.backend = None
        self.tui = None
        self.stop_requested = False
        self.quotas, self.errors = {}, {}
        self.identities = {}
        self.query_executor = ThreadPoolExecutor(max_workers=1)
        self.query_future = None
        self.query_cancel = threading.Event()
        self.quota_updated = False
        self.timings = []
        self.next_query = 0
        self.next_sync = 0
        self.active_turn = None
        self.waiting_user = False
        self.quota_failed = False
        self.closed = False
        self.account_locks = {}
        self.owns_session = False
        self.overrides = {}
        self.tui_options = []
        self.cwd_override = None
        self.terminal = None
        self.warnings = []

    def _record_timing(self, phase, start):
        self.timings.append({"phase": phase, "elapsed_ms": round((time.monotonic() - start) * 1000, 2)})
        if self.session:
            with contextlib.suppress(OSError):
                for measurement in self.timings:
                    self.session.log("timing", **measurement)
            self.timings.clear()

    @timed
    def _cancel_query(self):
        self.query_cancel.set()
        if self.query_future:
            self.query_future.cancel()
            # Running RPC waits observe the event; their query-only processes
            # are reaped by the workers before the executor is joined.
            with contextlib.suppress(Exception):
                self.query_future.result()
            self.query_future = None
        self.query_cancel = threading.Event()

    def _query(self, cancel_event, active=None):
        return codex.query_all(self.config, self.runtime / "query", cancel_event=cancel_event, active=active)

    def _save_quotas(self):
        if self.session:
            self.session.state["quotas"] = {n: dataclasses.asdict(q) for n, q in self.quotas.items()}
            self.session.state["quota_errors"] = self.errors
            self.session.save()

    @timed
    def _select_account(self, order, drain_order=()):
        """Only block on candidates before the first usable account in order.

        A successful preflight backend becomes the execution backend.
        """
        self._cancel_query()
        order, drain_order = list(order), list(drain_order)
        self.quotas, self.errors = {}, {}

        def probe(name):
            if self.stop_requested:
                raise codex.QueryCancelled("额度查询已取消")
            deadline = time.monotonic() + self.config.query_timeout
            backend = self._start_backend(name, preflight=True, deadline=deadline)
            quota = codex.read_quota(self.config, name, backend.rpc, backend.account_info,
                               cancel_event=self.query_cancel, deadline=deadline)
            self.quotas[name] = quota
            return quota

        try:
            for name in order:
                try:
                    quota = probe(name)
                    if quota.available(self.config.threshold):
                        return name
                except codex.QueryCancelled:
                    raise
                except (PoolError, OSError, subprocess.SubprocessError) as exc:
                    self.errors[name] = str(exc)
                self._discard_preflight()
            # All candidates are below threshold. Preserve the existing drain
            # rules, and recheck a reopened fallback before starting any turn.
            for name in drain_order:
                if name in self.errors or name not in self.quotas or self.quotas[name].exhausted:
                    continue
                try:
                    if not probe(name).exhausted:
                        return name
                except codex.QueryCancelled:
                    raise
                except (PoolError, OSError, subprocess.SubprocessError) as exc:
                    self.errors[name] = str(exc)
                self._discard_preflight()
            return None
        finally:
            self.next_query = time.monotonic() + self.config.poll_seconds
            self._save_quotas()

    def _discard_preflight(self):
        if self.backend:
            self.backend.close(timeout=.2)
            self.backend = None
        if self.session:
            self.session.state["backend"] = None
            self.session.save()

    def _lock_accounts(self, homes):
        acquired = {}
        try:
            for home in sorted(set(homes.values())):
                check_home_layout(home)
                if home not in self.account_locks:
                    acquired[home] = Lock(home / "quota-pool.lock")
        except BaseException:
            for lock in acquired.values():
                lock.close()
            raise
        self.account_locks.update(acquired)

    def notify(self, text):
        if self.session:
            self.session.log("notice", message=text)

    def warn(self, text):
        self.notify(text)
        if self.terminal is None:
            print(text, file=sys.stderr, flush=True)
        elif text not in self.warnings:
            self.warnings.append(text)

    def _backend_record(self, preflight=False):
        if not self.backend:
            return None
        return {**codex.process_record(self.backend.proc.pid), "port": self.backend.port,
                "token_file": str(self.backend.token_path), "query_only": preflight}

    @timed
    def _start_backend(self, account, preflight=False, deadline=None):
        if self.backend:
            if self.backend.account != account:
                raise PoolError("旧后端尚未停止，拒绝启动另一账号")
            if not preflight and self.session:
                self.session.state["backend"] = self._backend_record()
                self.session.save()
            return self.backend
        s = self.session
        directory = s.directory / "backends" / str(time.time_ns()) if s else self.runtime / "startup" / str(time.time_ns())
        cwd = str(self.cwd_override or s.state["cwd"]) if s else self.cwd
        options = {"cancel_event": self.query_cancel, "deadline": deadline} if preflight else {}
        backend = codex.Backend(self.config, account, cwd, directory, **options)
        try:
            account_info, identity = codex.read_account(backend.rpc, **options)
            if account in self.identities and self.identities[account] != identity:
                raise PoolError("账号登录身份已改变，请重新运行额度检查")
            if s:
                expected = s.state.get("identities", {}).get(account)
                if expected and identity != expected:
                    raise PoolError(f"{account} 已更换登录账号，请先重新确认账号配置")
                codex.verify_model(backend.rpc, {**s.state["settings"], **self.overrides}, **options)
            if any(name != account and name in self.config.accounts and value == identity
                   for name, value in self.identities.items()):
                raise PoolError("与池内另一名称使用了相同的登录账号")
            self.identities[account] = identity
            backend.account_info = account_info
            self.backend = backend
            if s:
                s.state.setdefault("identities", {})[account] = identity
                s.state["backend"] = self._backend_record(preflight)
                s.save()
            return backend
        except BaseException:
            backend.close(timeout=.2 if preflight else 5)
            raise

    @timed
    def create(self, cwd, model=None):
        self.cwd = str(Path(cwd).expanduser().resolve())
        if not Path(self.cwd).is_dir():
            raise PoolError(f"项目目录不存在：{self.cwd}")
        self._lock_accounts(self.config.homes)
        account = self._select_account(self.config.accounts, self.config.accounts)
        if account is None:
            raise PoolError("所有账号额度耗尽或不可查询；请运行 status --refresh 查看原因")
        backend = self._start_backend(account)
        params = {"cwd": self.cwd, "serviceName": "codex-quota-pool"}
        if model:
            params["model"] = model
        params.update(self.overrides)
        result = backend.rpc.call("thread/start", params)
        # Empty threads are lazy-persisted in 0.163.0. Naming materializes the
        # thread without inventing a message or spending model quota.
        backend.rpc.call("thread/name/set", {"threadId": result["thread"]["id"],
                                              "name": "额度池 · " + result["thread"]["id"][:8]})
        self.session = Session.create(self.runtime, result["thread"]["id"], account,
                                      self.config.homes, self.cwd, codex.saved_settings(result))
        self.owns_session = True
        self.session.state["backend"] = self._backend_record()
        self.session.state["identities"] = self.identities
        self.session.state["launch_config"] = copy.deepcopy(params.get("config", {}))
        self.overrides = {}
        self.cwd_override = None
        self.session.save()
        self._save_quotas()
        self._sync_retry()
        return self.session


    @timed
    def attach(self, session):
        state = session.state
        if codex.alive(state.get("controller")):
            raise PoolError("这个会话已有控制器在运行")
        self._lock_accounts({**{k: Path(v) for k, v in state["homes"].items()}, **self.config.homes})
        self.session = session
        self.owns_session = True
        self._update_membership()
        if codex.alive(state.get("backend")):
            self.notify("正在收回上次意外退出后遗留的后端……")
            record = state["backend"]
            path = Path(record["token_file"]).resolve()
            if not path.is_relative_to(self.runtime.resolve()):
                raise PoolError("后端认证文件不在额度池运行目录内")
            if not record.get("query_only"):
                rpc = codex.WebSocketRpc(record["port"], path.read_text(), self.config.query_timeout)
                try:
                    codex.terminate_record(state.get("tui"))
                    paused, interrupted = codex.interrupt_tree(rpc, Path(state["homes"][state["active_account"]]), state["id"])
                    state["resume_pending"] = bool(interrupted or paused or state.get("resume_pending"))
                    state["paused_goals"] = list(set(state.get("paused_goals", []) + paused))
                finally:
                    rpc.close()
            codex.terminate_record(record, group=True)
        codex.terminate_record(state.get("tui"))
        state["backend"], state["tui"] = None, None
        if state.get("pending_turn"):
            state["needs_review"] = True
            self.warn("上次发送消息的结果不确定，恢复后请在终端核验；程序不会重复发送该消息。")
        session.save()
        # A different native Codex process must not still own the source.
        with Lock(Path(state["homes"][state["active_account"]]) / "thread-writer-locks" / (state["id"] + ".lock")):
            self._sync_retry(frozen=True)

    def _update_membership(self):
        state = self.session.state
        for name in self.config.accounts:
            new_home = str(self.config.homes[name])
            if name in state["homes"] and state["homes"][name] != new_home:
                raise PoolError(f"{name} 的目录改变了；已有会话不允许重定向账号目录")
            state["homes"][name] = new_home
        self.session.save()

    @timed
    def _sync_retry(self, frozen=False):
        # A pending checkpoint is first completed, then a fresh source snapshot is
        # taken; this preserves progress made before a failed live sync froze.
        for attempt in range(3):
            try:
                was_pending = bool(self.session.state.get("pending_sync"))
                checkpoint = Syncer(self.session).sync(self.config.accounts, frozen=frozen)
                if was_pending:
                    checkpoint = Syncer(self.session).sync(self.config.accounts, frozen=frozen)
                self.next_sync = time.monotonic() + self.config.sync_seconds
                return checkpoint
            except (PoolError, OSError) as exc:
                if attempt == 2 or "分叉" in str(exc) or "覆盖" in str(exc) or "正在使用" in str(exc):
                    raise
                time.sleep(.2)

    @timed
    def _close_tui(self):
        if self.terminal is not None:
            terminal, self.terminal = self.terminal, None
            terminal.close()
            self.stop_requested |= terminal.interrupted.is_set()
            if terminal.error:
                self.warn(f"终端连接中断：{terminal.error}")
        self.tui = None
        if self.session:
            self.session.state["tui"] = None
            self.session.save()

    @timed
    def freeze(self, reason):
        if self.terminal:
            self.terminal.stop_input.set()
        self._cancel_query()
        state = self.session.state
        state["status"] = "pausing"
        state["pause_reason"] = reason
        self.session.save()
        if self.backend and (state.get("backend") or {}).get("query_only"):
            self._discard_preflight()
        if self.backend:
            # Stop input first, then interrupt via RPC before gracefully closing
            # the UI. Otherwise its Ctrl+C can interrupt the turn before we record
            # it, losing the continuation needed for an automatic quota handoff.
            terminal = self.terminal
            if terminal:
                terminal.stop_input.set()
            else:
                self._close_tui()
            home = Path(state["homes"][state["active_account"]])
            try:
                result = self.backend.rpc.call("thread/resume", {"threadId": state["id"], "excludeTurns": True})
                state["settings"] = codex.saved_settings(result)
                paused, interrupted = codex.interrupt_tree(self.backend.rpc, home, state["id"])
            finally:
                if terminal:
                    self._close_tui()
            if terminal:
                # Also quiesce a prompt that was already queued inside the UI
                # before input was disabled (notably a very early startup exit).
                late_paused, late_interrupted = codex.interrupt_tree(self.backend.rpc, home, state["id"])
                paused += late_paused
                interrupted |= late_interrupted
            state["paused_goals"] = list(set(state.get("paused_goals", []) + paused))
            state["resume_pending"] = bool(interrupted or paused or self.quota_failed)
            # Drain final usage without replaying turn/started side effects such
            # as reactivating a goal that codex.interrupt_tree has just paused.
            for event in self.backend.rpc.drain():
                self._capture_usage(event)
                if event.get("method") == "turn/started" and event.get("params", {}).get("threadId") == state["id"]:
                    state["pending_turn"] = None
            self.backend.close()
            self.backend = None
            state["backend"] = None
            self.session.save()
        checkpoint = self._sync_retry(frozen=True)
        usage = checkpoint_usage(checkpoint, state["id"])
        if usage is not None:
            state["token_usage"] = usage
        state.pop("sync_error", None)
        self.session.save()
        self.active_turn = None
        self.waiting_user = False
        self.quota_failed = False

    def launch(self, account, prompt=None):
        if self.stop_requested:
            self.pause_finished("paused_user")
            return
        state = self.session.state
        if self.cwd_override and not self.cwd_override.is_dir():
            raise PoolError(f"项目目录不存在：{self.cwd_override}")
        # The account selection is durable before any new model request.
        state["active_account"] = account
        state["status"] = "starting"
        self.session.save()
        backend = self._start_backend(account)
        params = codex.resume_params(state)
        params["config"] = codex.merge_config(params["config"], self.overrides.get("config", {}))
        params.update({key: value for key, value in self.overrides.items() if key != "config"})
        if self.cwd_override:
            params["cwd"] = str(self.cwd_override)
        result = backend.rpc.call("thread/resume", params)
        try:
            expected = dict(state["settings"])
            if "approvalPolicy" in self.overrides:
                expected["approvalPolicy"] = self.overrides["approvalPolicy"]
            if self.cwd_override or "sandbox" in self.overrides or "sandbox_workspace_write" in self.overrides.get("config", {}):
                # A user-requested directory/sandbox change intentionally changes
                # its materialized roots. Subsequent handoffs verify it exactly.
                expected["sandbox"] = result["sandbox"]
            codex.verify_permissions(expected, result)
            # /plan and /fast are native settings. Restore them without sending
            # a model turn; this also preserves changes made just before exit.
            sticky = {key: state["settings"][key] for key in ("collaborationMode", "serviceTier", "disabledPluginIds")
                      if key in state["settings"]}
            if sticky.get("collaborationMode") and "model" in self.overrides:
                sticky = copy.deepcopy(sticky)
                sticky["collaborationMode"]["settings"]["model"] = self.overrides["model"]
            if sticky:
                backend.rpc.call("thread/settings/update", {"threadId": state["id"], **sticky})
                result = backend.rpc.call("thread/resume", {"threadId": state["id"], "excludeTurns": True})
        except PoolError:
            backend.close()
            self.backend = None
            state["backend"] = None
            self.session.save()
            raise
        state["settings"] = codex.saved_settings(result)
        state["cwd"] = result.get("cwd", params["cwd"])
        state["launch_config"] = codex.merge_config(state.get("launch_config", {}), self.overrides.get("config", {}))
        self.overrides = {}
        self.cwd_override = None
        self.session.save()
        self.start_tui(prompt)
        state["status"] = "running" if prompt else "idle"
        self.session.save()

    @timed
    def start_tui(self, prompt=None):
        state = self.session.state
        account = state["active_account"]
        self.notify(f"额度池会话 {state['id']}，当前账号：{account}")
        env = self.config.env(account)
        env["CODEX_POOL_BACKEND_TOKEN"] = self.backend.token
        command = [self.config.binary, "resume", "--remote", self.backend.address,
                   "--remote-auth-token-env", "CODEX_POOL_BACKEND_TOKEN", *self.tui_options, "--", state["id"]]
        if prompt:
            # Let the native terminal submit the prompt after its subscription
            # is ready. Approval and question requests then have a live UI owner.
            state["pending_turn"] = {"prompt": prompt, "at": time.time(), "via": "terminal"}
            self.session.save()
            command.append(prompt)
        self.terminal = TerminalRelay(command, env=env, cwd=state["cwd"])
        self.tui = self.terminal.proc
        state["tui"] = codex.process_record(self.tui.pid)
        self.session.save()


    def _capture_usage(self, event):
        params = event.get("params", {})
        if event.get("method") == "thread/tokenUsage/updated" and params.get("threadId") == self.session.state["id"]:
            usage = normalize_usage(params.get("tokenUsage", {}).get("total"))
            if usage is not None:
                self.session.state["token_usage"] = usage
                self.session.save()

    def _events(self):
        if not self.backend:
            return
        state = self.session.state
        for event in self.backend.rpc.drain():
            self._capture_usage(event)
            method, params = event.get("method"), event.get("params", {})
            if method == "account/rateLimits/updated":
                active = state["active_account"]
                try:
                    quota = codex.Quota.parse(params, self.config.limit_ids.get(active, "codex"))
                except PoolError:
                    # Partial notifications cannot establish that both windows
                    # are usable. Refresh them through the existing connection.
                    self.next_query = 0
                else:
                    self.quotas[active] = quota
                    self.errors.pop(active, None)
                    self.quota_updated = True
                    self._save_quotas()
                    if not quota.available(self.config.threshold):
                        self.next_query = 0
            if params.get("threadId") != state["id"]:
                continue
            if method == "turn/started":
                self.active_turn = params["turn"]["id"]
                if state.get("pending_turn") and state["id"] in state.get("paused_goals", []):
                    self.backend.rpc.call("thread/goal/set", {"threadId": state["id"], "status": "active", "origin": "user"})
                    state["paused_goals"].remove(state["id"])
                state["pending_turn"] = None
                state["resume_pending"] = True
                state["status"] = "running"
                self.session.save()
            elif method == "turn/completed":
                self.active_turn = None
                turn = params["turn"]
                error = (turn.get("error") or {}).get("codexErrorInfo")
                self.quota_failed = turn["status"] == "failed" and error == "usageLimitExceeded"
                state["status"] = "quota_exhausted" if self.quota_failed else "idle"
                state["last_turn_status"] = turn["status"]
                state["resume_pending"] = self.quota_failed
                self.next_sync = 0
                if self.quota_failed:
                    self.next_query = 0
                self.session.save()
            elif method == "thread/status/changed":
                flags = params.get("status", {}).get("activeFlags", [])
                self.waiting_user = any("waiting" in str(flag).lower() for flag in flags)
            elif method in ("item/completed", "thread/goal/updated"):
                self.next_sync = min(self.next_sync, time.monotonic() + 1)


    def _poll(self):
        if self.query_future and self.query_future.done():
            quotas, errors, identities = self.query_future.result()
            self.query_future = None
            # A notification received during polling is more recent than that sample.
            for name, quota in self.quotas.items():
                if name in quotas and quota.sampled_at > quotas[name].sampled_at:
                    quotas[name] = quota
            self.quotas, self.errors = quotas, errors
            self.identities.update(identities)
            self._save_quotas()
            self.next_query = time.monotonic() + self.config.poll_seconds
            return True
        if self.query_future is None and time.monotonic() >= self.next_query:
            active = (self.backend.account, self.backend.rpc) if self.backend else None
            self.query_future = self.query_executor.submit(self._query, self.query_cancel, active)
        return False

    def _resume_available(self, order, drain_order=(), prompt=None, denied=False):
        target = self._select_account(order, drain_order)
        if target:
            self.launch(target, prompt)
            return True
        current = self.quotas.get(self.session.state["active_account"])
        self.pause_finished("paused_quota" if denied or current and current.exhausted else "paused_query")
        return False

    def _apply_policy(self):
        state = self.session.state
        active = state["active_account"]
        quotas = dict(self.quotas)
        if self.quota_failed:
            quotas[active] = codex.Quota(0, [], True)
        action, _ = codex.decision(active, self.config.accounts, quotas, self.config.threshold)
        if self.waiting_user or state.get("pending_turn"):
            return
        if not self.active_turn and not self.quota_failed and active in self.config.accounts:
            return  # Keep unsent input in the idle native terminal.
        if action in ("switch", "pause"):
            denied = self.quota_failed
            self.freeze("quota_switch" if action == "switch" else "quota_exhausted")
            if self.stop_requested:
                self.pause_finished("paused_user")
                return
            order = list(self.config.accounts)
            if active in order:
                index = order.index(active)
                order = order[index + 1:] + order[:index]
            # Recheck candidates after the old task has stopped. The current account
            # may drain its remainder only if the server has not denied its usage.
            fallback = [active] if active in self.config.accounts and not denied else []
            prompt = CONTINUE if state.get("resume_pending") else None
            self._resume_available(order + fallback, fallback, prompt, denied=denied)
        elif action == "drain" and state["status"] != "draining":
            state["status"] = "draining"
            self.session.save()

    def pause_finished(self, status):
        self.session.state["status"] = status
        self.session.save()
        self.notify(f"已暂停，所有副本同步到 v{self.session.state['revision']}。")

    def loop(self, prompt=None):
        state = self.session.state
        state["controller"] = codex.process_record(os.getpid())
        self.session.save()
        previous_handlers = {}
        exit_code = 0

        def signal_handler(signum, _frame):
            self.stop_requested = True
            self.query_cancel.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[sig] = signal.signal(sig, signal_handler)
        try:
            if self.backend:
                self.start_tui(prompt)
            else:
                active = state["active_account"]
                order = list(self.config.accounts)
                if active in order:
                    index = order.index(active)
                    order = [active] + order[index + 1:] + order[:index]
                self._resume_available(order, [active] if active in order else [], prompt)
            while True:
                if self.terminal and self.terminal.interrupted.is_set():
                    self.stop_requested = True
                if self.stop_requested:
                    self.freeze("user_pause")
                    self.pause_finished("paused_user")
                    break
                if self.tui and self.tui.poll() is not None:
                    code = self.tui.returncode
                    exit_code = code if code >= 0 else 128 - code
                    self.freeze("terminal_closed")
                    if exit_code not in (0, 130):
                        state["error"] = f"Codex 界面退出，状态码 {exit_code}"
                        self.warn(state["error"])
                        self.pause_finished("paused_error")
                    else:
                        self.pause_finished("paused_user")
                    break
                self._events()
                if self.backend and self.backend.rpc.closed:
                    raise PoolError("Codex 后端连接意外断开；请恢复会话以核验最后进度")
                fresh = self._poll()
                if self.backend and time.monotonic() >= self.next_sync:
                    self._sync_retry()
                    self.next_sync = time.monotonic() + self.config.sync_seconds
                if (fresh or self.quota_updated) and self.backend:
                    self.quota_updated = False
                    self._apply_policy()
                if not self.backend:
                    if state["status"] not in ("paused_quota", "paused_query") or not self.config.resume_when_available:
                        break
                    if fresh:
                        target = next((n for n in self.config.accounts if n in self.quotas and self.quotas[n].available(self.config.threshold)), None)
                        if target:
                            self._sync_retry(frozen=True)
                            prompt = CONTINUE if state.get("resume_pending") and not state.get("needs_review") else None
                            self._resume_available(self.config.accounts, prompt=prompt)
                time.sleep(.15)
        except codex.QueryCancelled:
            if not self.stop_requested:
                raise
            self.freeze("user_pause")
            self.pause_finished("paused_user")
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                message = "控制器被中断"
            else:
                message = str(exc)
            try:
                self.freeze("controller_error")
            except Exception as freeze_error:
                state["sync_error"] = str(freeze_error)
            state["status"] = "paused_error"
            state["error"] = message
            self.session.save()
            raise
        finally:
            for sig, handler in previous_handlers.items():
                signal.signal(sig, handler)
            self.close()
        return exit_code

    def close(self):
        if self.closed:
            return
        self.closed = True
        started = time.monotonic()
        self._cancel_query()
        self._close_tui()
        if self.backend:
            self.backend.close()
            self.backend = None
            if self.session:
                self.session.state["backend"] = None
        self.query_executor.shutdown(wait=True, cancel_futures=True)
        if self.session and self.owns_session:
            self.session.state["controller"] = None
            self.session.save()
        for lock in self.account_locks.values():
            lock.close()
        self.account_locks.clear()
        self._record_timing("close", started)
