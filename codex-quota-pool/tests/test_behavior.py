"""Unit coverage for the three commands, quotas and prompt/exit behavior."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch
import base64
import contextlib
import dataclasses
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
from quota_pool.cli import Config, ROOT, main, parse_args, resume_hint, select_resume, quota_table, usage_line
from quota_pool.pool import Pool
from quota_pool.codex import Quota, decision, next_account, Rpc, QueryCancelled, query_account, query_all, RpcError
from quota_pool.session import PoolError, Session, checkpoint_usage, normalize_usage
from quota_pool.terminal import ANSI, ExitOutput, InputFilter
from fixtures import fixture

def q(remaining):
    return Quota(remaining, [], remaining == 0)


class PolicyTests(unittest.TestCase):
    def test_order_drain_and_exhaustion(self):
        order = ["a", "b", "c"]
        quotas = {"a": q(9), "b": q(100), "c": q(100)}
        self.assertEqual(decision("a", order, quotas, 10), ("switch", "b"))
        quotas["b"] = q(9)
        self.assertEqual(decision("b", order, quotas, 10), ("switch", "c"))
        quotas["c"] = q(9)
        self.assertEqual(decision("c", order, quotas, 10), ("drain", None))
        quotas["c"] = q(0)
        self.assertEqual(decision("c", order, quotas, 10), ("pause", None))
        quotas["a"] = q(100)
        self.assertEqual(decision("c", order, quotas, 10), ("switch", "a"))

    def test_threshold_is_strict_and_does_not_preempt_healthy_writer(self):
        self.assertEqual(decision("b", ["a", "b"], {"a": q(100), "b": q(10)}, 10), ("continue", None))

    def test_unknown_does_not_trigger_failover_or_claim_eligibility(self):
        self.assertEqual(decision("a", ["a", "b"], {"b": q(80)}, 10), ("unknown", None))
        self.assertEqual(decision("a", ["a", "b"], {"a": q(5)}, 10), ("drain", None))

    def test_both_windows_and_backend_denial(self):
        response = {"rateLimits": {"limitId": "codex", "primary": {"usedPercent": 5, "windowDurationMins": 300},
                                   "secondary": {"usedPercent": 98, "windowDurationMins": 10080}}}
        quota = Quota.parse(response)
        self.assertEqual(quota.remaining, 95)
        self.assertTrue(quota.available(10))
        response["ordinaryUsageAllowed"] = False
        self.assertTrue(Quota.parse(response).exhausted)

    def test_weekly_zero_and_five_hour_threshold(self):
        for week, five, exhausted, available in [(0.5, 80, False, True), (0, 80, True, False),
                                                  (90, 0, True, False), (90, 1, False, True),
                                                  (90, .5, False, False)]:
            with self.subTest(week=week, five=five):
                # Deliberately reverse the primary/secondary positions.
                quota = Quota.parse({"rateLimits": {
                    "primary": {"usedPercent": 100 - week, "windowDurationMins": 10080},
                    "secondary": {"usedPercent": 100 - five, "windowDurationMins": 300}}})
                self.assertEqual(quota.exhausted, exhausted)
                self.assertEqual(quota.available(1), available)

    def test_missing_unknown_duplicate_windows_are_not_eligible(self):
        for first, second in [(300, None), (10080, None), (15, 10080), (300, 300), (None, None)]:
            with self.subTest(first=first, second=second):
                bucket = {"primary": {"usedPercent": 10, "windowDurationMins": first}}
                if second is not None:
                    bucket["secondary"] = {"usedPercent": 10, "windowDurationMins": second}
                with self.assertRaises(PoolError):
                    Quota.parse({"rateLimits": bucket})
        self.assertTrue(Quota.parse({"rateLimits": {"primary": {
            "usedPercent": 100, "windowDurationMins": 10080}}}).exhausted)
        self.assertTrue(Quota.parse({"ordinaryUsageAllowed": False, "rateLimits": {
            "primary": {"usedPercent": 10, "windowDurationMins": 15}}}).exhausted)

    def test_wrong_bucket_and_invalid_values(self):
        for response in [
            {"rateLimits": {"limitId": "other", "primary": {"usedPercent": 1}}},
            {"rateLimitsByLimitId": {"other": {}}, "rateLimits": {"primary": {"usedPercent": 1}}},
            {"rateLimits": {}},
            *({"rateLimits": {"primary": {"usedPercent": x}}} for x in (True, -1, 101, float("nan"), "9")),
        ]:
            with self.subTest(response=response), self.assertRaises(PoolError):
                Quota.parse(response)

    def test_reorder_and_removal(self):
        self.assertEqual(next_account(["c", "b", "a"], "c", {"a": q(99), "b": q(99)}, 10), "b")
        self.assertEqual(decision("a", ["b"], {"a": q(99), "b": q(9)}, 10), ("pause", None))


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "config.json"
        self.raw = {"accounts": ["a", "b"], "account_homes": {"a": str(self.root / "a"), "b": str(self.root / "b")},
                    "switch_below_percent": 10, "poll_seconds": 15, "codex_binary": shutil.which("python3")}

    def load(self):
        self.path.write_text(json.dumps(self.raw))
        return Config.load(self.path)

    def test_config_changes_take_effect_only_on_restart(self):
        original = self.load()
        pool = Pool(original, self.root / "runtime")
        self.addCleanup(pool.close)
        self.raw["poll_seconds"] = 3
        changed = self.load()
        self.assertEqual(pool.config.poll_seconds, 15)
        restarted = Pool(changed, self.root / "new-runtime")
        self.addCleanup(restarted.close)
        self.assertEqual(restarted.config.poll_seconds, 3)
        self.path.write_text('{"accounts":')
        with self.assertRaises(PoolError):
            Config.load(self.path)

    def test_reject_aliases_pointing_to_same_home(self):
        self.raw["account_homes"]["b"] = self.raw["account_homes"]["a"]
        with self.assertRaises(PoolError):
            self.load()

    def test_external_database_layout_is_rejected_before_start(self):
        config = self.load()
        for home in config.homes.values():
            home.mkdir()
        (config.homes["a"] / "config.toml").write_text('sqlite_home = "/another/database"\n')
        controller = Pool(config, self.root / "runtime")
        self.addCleanup(controller.close)
        with patch("quota_pool.codex.Backend") as query:
            with self.assertRaisesRegex(PoolError, "sqlite_home"):
                controller.create(self.root)
            query.assert_not_called()
        self.assertFalse((config.homes["a"] / "quota-pool.lock").exists())

    def test_explicit_proxy_applies_without_shell_proxy(self):
        self.raw["proxy_env"] = {"HTTPS_PROXY": "http://127.0.0.1:7897", "https_proxy": "http://127.0.0.1:7897"}
        config = self.load()
        with patch.dict("os.environ", {}, clear=True):
            for account in config.accounts:
                env = config.env(account)
                self.assertEqual(env["HTTPS_PROXY"], "http://127.0.0.1:7897")
                self.assertEqual(env["https_proxy"], env["HTTPS_PROXY"])
                self.assertEqual(env["CODEX_HOME"], str(config.homes[account]))

    def test_invalid_and_misspelled_settings(self):
        for key, value in [("poll_seconds", 0), ("switch_below_percent", True),
                           ("resume_when_available", "false"), ("accounts", ["a", "a"]), ("poll_second", 15)]:
            with self.subTest(key=key):
                previous = dict(self.raw)
                self.raw[key] = value
                with self.assertRaises(PoolError):
                    self.load()
                self.raw = previous


class FrontendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cdx cli ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "project one"
        self.project.mkdir()
        self.runtime = self.root / "runtime"
        self.config = self.root / "config.json"
        self.config.write_text(json.dumps({"accounts": ["test"],
                                          "account_homes": {"test": str(self.root / "account")},
                                          "codex_binary": sys.executable}))

    def session(self, cwd):
        return Session.create(self.runtime, str(uuid.uuid4()), "a", {"a": self.root / "a"}, cwd, {})

    def args(self, *argv):
        return parse_args(["--pool-config", str(self.config), "--pool-runtime", str(self.runtime), *argv])

    def test_installed_symlink_keeps_caller_directory_and_finds_config(self):
        # A clean checkout has no private config and may have no Codex binary.
        install = self.root / "installation"
        install.mkdir()
        shutil.copy2(ROOT / "cdx", install / "cdx")
        shutil.copytree(ROOT / "quota_pool", install / "quota_pool",
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(self.config, install / "config.json")
        link = self.root / "cdx"
        link.symlink_to(install / "cdx")
        result = subprocess.run([str(link), "--version"], cwd=self.project, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Python", result.stdout)
        self.assertEqual(list(self.project.iterdir()), [])

    def test_make_install_is_idempotent_and_preserves_other_commands(self):
        target = self.root / "bin"
        command = ["make", "-C", str(ROOT), "install", "BIN_DIR=" + str(target)]
        for _ in range(2):
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((target / "cdx").resolve(), ROOT / "cdx")
        (target / "cdx").unlink()
        (target / "cdx").write_text("existing command")
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((target / "cdx").read_text(), "existing command")


    def test_native_arguments_before_and_after_resume(self):
        tid = str(uuid.uuid4())
        args = self.args("-m", "test-model", "resume", tid, "-C", str(self.project), "continue this task")
        self.assertEqual((args.command, args.session, args.prompt), ("resume", tid, "continue this task"))
        self.assertEqual(args.cwd, self.project)
        self.assertEqual(args.overrides["model"], "test-model")

    def test_literal_reserved_word_and_dash_prompt(self):
        for prompt in ("resume", "--help", "task; $(false) 'quoted'"):
            args = self.args("-m", "test", "--", prompt)
            self.assertEqual((args.command, args.prompt), ("run", prompt))

    def test_rejects_unknown_and_conflicting_flags(self):
        for argv in (("--remote", "ws://elsewhere"), ("resume", "--last", str(uuid.uuid4())),
                     ("--refesh",), ("status", "-m", "test"), ("resume", "--from", "a")):
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                self.args(*argv)

    def test_last_scopes_by_project_and_all_is_explicit(self):
        matching = self.session(self.project)
        other = self.session(self.root)
        args = self.args("resume", "--last", "-C", str(self.project))
        self.assertEqual(select_resume(args).state["id"], matching.state["id"])
        args.all = True
        self.assertEqual(select_resume(args).state["id"], other.state["id"])
        args.all, args.cwd = False, self.root / "missing"
        with self.assertRaisesRegex(PoolError, "没有池内会话"):
            select_resume(args)

    def test_explicit_id_works_from_another_project_and_picker_can_cancel(self):
        session = self.session(self.project)
        args = self.args("resume", session.state["id"], "-C", str(self.root))
        self.assertEqual(select_resume(args).state["id"], session.state["id"])
        args.session, args.all = None, True
        with patch("builtins.input", return_value="q"), contextlib.redirect_stdout(io.StringIO()):
            self.assertIsNone(select_resume(args))

    def test_resume_hint_can_be_pasted_with_custom_paths(self):
        session = self.session(self.project)
        session.state["last_sync_frozen"] = True
        args = self.args("--pool-config", str(self.root / "settings 'one'.json"))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            resume_hint(args, session)
        command = shlex.split(output.getvalue().splitlines()[-1])
        restored = parse_args(command[1:])
        self.assertEqual(restored.config, args.config)
        self.assertEqual(restored.runtime, args.runtime)
        self.assertEqual(restored.session, session.state["id"])

    def test_exit_summary_has_only_usable_command_and_actual_usage(self):
        session = self.session(self.project)
        session.state.update(last_sync_frozen=True, status="paused_user",
                             token_usage={"input_tokens": 10, "cached_input_tokens": 0,
                                          "output_tokens": 10, "reasoning_output_tokens": 0})
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            resume_hint(parse_args([]), session)
        self.assertEqual(output.getvalue(), f"To reconnect, run:\n  cdx resume {session.state['id']}\n\n"
                                           "Token usage so far: total=20 input=10 output=10\n")
        self.assertEqual(errors.getvalue(), "")

    def test_failed_sync_still_warns_and_offers_recovery(self):
        session = self.session(self.project)
        session.state.update(status="paused_error", pending_sync={"revision": 2})
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            resume_hint(parse_args([]), session, ["测试诊断：同步写入失败"])
        self.assertIn("同步写入失败", errors.getvalue())
        self.assertIn("保存同步尚未完成", errors.getvalue())
        self.assertIn(f"cdx resume {session.state['id']}", output.getvalue())
        self.assertNotIn("Token usage", output.getvalue())

    def test_user_resume_opens_composer_without_restarting_cancelled_work(self):
        session = self.session(self.project)
        session.state["resume_pending"] = True
        session.state["last_sync_frozen"] = True
        session.save()
        output = io.StringIO()
        with patch("quota_pool.codex.check_version"), patch("quota_pool.cli.Pool") as factory, \
                patch("sys.stdin.isatty", return_value=True), patch("sys.stdout.isatty", return_value=True), \
                contextlib.redirect_stdout(output):
            # StringIO replaces stdout, so its tty check needs its own patch.
            with patch.object(output, "isatty", return_value=True):
                controller = factory.return_value
                controller.session, controller.owns_session = session, True
                controller.loop.return_value = 130
                result = main(["--pool-config", str(self.config), "--pool-runtime", str(self.runtime),
                               "resume", session.state["id"]])
        self.assertEqual(result, 130)
        controller.loop.assert_called_once_with(None)
        controller.close.assert_called_once()
        self.assertIn("cdx", output.getvalue())
        self.assertIn(session.state["id"], output.getvalue())


class QueryLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pool-query-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        binary = self.root / "codex"
        helper = Path(__file__).with_name("fixtures.py")
        binary.write_text("#!/usr/bin/env python3\nimport runpy\nrunpy.run_path(" + repr(str(helper)) + ", run_name='__main__')\n")
        binary.chmod(0o700)
        homes = {n: self.root / n for n in ("a", "b")}
        for home in homes.values():
            home.mkdir()
            (home / "fixture.json").write_text('{}')
        self.config = Config(tuple(homes), homes, 10, 15, False, str(binary), query_timeout=30)

    def settings(self, **values):
        for home in self.config.homes.values():
            (home / "fixture.json").write_text(json.dumps(values))

    def wait_for_workers(self, names):
        deadline = time.monotonic() + 3
        paths = [self.config.homes[n] / "waiting.pid" for n in names]
        while time.monotonic() < deadline:
            if all(p.exists() and p.read_text().strip() for p in paths):
                return [int(p.read_text()) for p in paths]
            time.sleep(.01)
        self.fail("query processes did not start")

    def test_controller_exit_cancels_running_queries_and_reaps_processes(self):
        for method in ("initialize", "account/read", "account/rateLimits/read"):
            with self.subTest(method=method):
                for home in self.config.homes.values():
                    (home / "waiting.pid").unlink(missing_ok=True)
                self.settings(delay_method=method, ignore_term=True)
                controller = Pool(self.config, self.root / "runtime")
                self.addCleanup(controller.close)
                controller.query_future = controller.query_executor.submit(
                    controller._query, controller.query_cancel)
                pids = self.wait_for_workers(self.config.accounts)
                start = time.monotonic()
                controller.close()
                self.assertLess(time.monotonic() - start, 2)
                for pid in pids:
                    with self.assertRaises(ProcessLookupError):
                        os.kill(pid, 0)

    def test_timeout_is_shared_by_all_query_stages(self):
        self.settings(delay_method="all", delay=.12)
        config = dataclasses.replace(self.config, query_timeout=.2)
        start = time.monotonic()
        quotas, errors, identities = query_all(config, self.root)
        self.assertEqual(quotas, {})
        self.assertEqual(identities, {})
        self.assertEqual(set(errors), set(config.accounts))
        self.assertTrue(all("超时" in message for message in errors.values()))
        self.assertLess(time.monotonic() - start, 1)

    def test_cancelled_borrowed_transport_remains_open(self):
        self.settings(delay_method="account/rateLimits/read")
        cancel = threading.Event()
        with Rpc([self.config.binary], self.config.env("a"), self.root) as rpc:
            with ThreadPoolExecutor(max_workers=1) as executor:
                pending = executor.submit(query_account, self.config, "a", self.root, cancel, rpc)
                self.wait_for_workers(["a"])
                cancel.set()
                with self.assertRaises(QueryCancelled):
                    pending.result(timeout=1)
                self.assertIsNone(rpc.proc.poll())
                self.assertFalse(rpc.closed)

    def test_startup_reuses_first_eligible_backend_without_querying_next(self):
        backend = Mock(account="a", account_info={})
        backend.proc.pid = os.getpid()
        backend.port = 1
        backend.token_path = self.root / "token"
        backend_factory = Mock(return_value=backend)
        controller = Pool(self.config, self.root / "runtime")
        backend_patch = patch("quota_pool.codex.Backend", backend_factory)
        backend_patch.start()
        self.addCleanup(backend_patch.stop)
        controller.cwd = str(self.root)
        self.addCleanup(controller.close)
        with patch("quota_pool.codex.read_account", return_value=({}, "account-a")), \
                patch("quota_pool.codex.read_quota", return_value=Quota(80, [], False)) as quota:
            self.assertEqual(controller._select_account(self.config.accounts), "a")
            self.assertIs(controller._start_backend("a"), backend)
        backend_factory.assert_called_once()
        self.assertEqual(quota.call_count, 1)
        backend.close.assert_not_called()
        self.assertGreater(controller.next_query, time.monotonic())

    def test_exhaustion_checks_unqueried_candidates_before_pausing(self):
        homes = self.config.homes
        tid = fixture(homes["a"])
        controller = Pool(self.config, self.root / "runtime")
        self.addCleanup(controller.close)
        controller.session = Session.create(self.root / "runtime", tid, "a", homes, self.root, {})
        controller.quotas = {"a": Quota(0, [], True)}
        controller.active_turn = "working"
        with patch.object(controller, "freeze"), patch.object(controller, "launch") as launch, \
                patch.object(controller, "_select_account", return_value="b") as select, \
                contextlib.redirect_stdout(None):
            controller._apply_policy()
        select.assert_called_once_with(["b", "a"], ["a"])
        launch.assert_called_once()
        self.assertEqual(launch.call_args.args[0], "b")

    def test_poll_keeps_newer_quota_notifications(self):
        controller = Pool(self.config, self.root / "runtime")
        self.addCleanup(controller.close)
        tid = fixture(self.config.homes["a"])
        controller.session = Session.create(self.root / "runtime", tid, "a", self.config.homes, self.root, {})
        old, new = Quota(80, [], False, sampled_at=1), Quota(0, [], True, sampled_at=2)
        controller.quotas = {"a": new}
        controller.query_future = controller.query_executor.submit(lambda: ({"a": old}, {}, {}))
        controller.query_future.result()
        self.assertTrue(controller._poll())
        self.assertIs(controller.quotas["a"], new)

    def test_complete_quota_event_updates_policy_without_an_extra_query(self):
        controller = Pool(self.config, self.root / "runtime")
        self.addCleanup(controller.close)
        tid = fixture(self.config.homes["a"])
        controller.session = Session.create(self.root / "runtime", tid, "a", self.config.homes, self.root, {})
        controller.backend = Mock()
        controller.next_query = time.monotonic() + 15
        next_query = controller.next_query
        controller.backend.rpc.drain.return_value = [{"method": "account/rateLimits/updated", "params": {
            "rateLimits": {"primary": {"usedPercent": 20, "windowDurationMins": 300},
                           "secondary": {"usedPercent": 99.5, "windowDurationMins": 10080}}}}]
        controller._events()
        self.assertTrue(controller.quotas["a"].available(10))
        self.assertEqual(controller.next_query, next_query)
        self.assertTrue(controller.quota_updated)

    def test_status_shows_both_windows_and_unknown_values(self):
        config = dataclasses.replace(self.config, accounts=("a",))
        windows = [{"window_minutes": 300, "remaining_percent": 80},
                   {"window_minutes": 10080, "remaining_percent": .5}]
        table = quota_table(config, {"quotas": {"a": {"windows": windows}}})
        self.assertIn("80%", table)
        self.assertIn("0.5%", table)
        self.assertIn("未知", quota_table(config, {"quotas": {}}))
        self.assertIn("network unavailable", quota_table(config, {"errors": {"a": "network unavailable"}}))


class RpcErrorTests(unittest.TestCase):
    def test_errors_distinguish_network_auth_and_permissions(self):
        cases = [
            ("workspace routing discovery timed out", "proxy_env"),
            ("error sending request for url", "proxy_env"),
            ("token refresh failed: connection refused", "proxy_env"),
            ("refresh_token_expired", "重新登录"),
            ("unexpected status code: 401", "HTTP 401"),
            ("Permission denied (os error 13)", "目录权限"),
        ]
        for message, hint in cases:
            with self.subTest(message=message):
                error = RpcError("account/read", {"code": -32603, "message": message})
                self.assertIn(hint, str(error))
                self.assertIn("-32603", str(error))

    def test_upstream_tokens_and_personal_details_are_not_displayed(self):
        for message in [
            "error sending request for url https://user:secret@example.org/?access_token=private-token",
            "unexpected internal error: private-token user@example.org",
        ]:
            error = RpcError("account/read", {"code": -32603, "message": message,
                                              "data": {"refresh_token": "private-refresh-token"}})
            for secret in ("secret", "private-token", "example.org", "private-refresh-token"):
                self.assertNotIn(secret, str(error))


class TerminalFilterTests(unittest.TestCase):
    def test_keyboard_stream_fragmentation_and_paste(self):
        for key in (b"\x03", b"\x1b[99;5u", b"\x1b[99;5:1u", b"\x1b[27;5;99~"):
            with self.subTest(key=key):
                parser = InputFilter()
                paste = b"\x1b[200~" + key + "中文\n".encode() + b"\x1b[201~"
                self.assertEqual(b"".join(parser.feed(bytes([c])) for c in paste), paste)
                self.assertFalse(parser.interrupted)
                self.assertEqual(b"".join(parser.feed(bytes([c])) for c in key), b"")
                self.assertTrue(parser.interrupted)

    def test_native_keys_and_escape(self):
        parser = InputFilter()
        keys = b"/plan\r\x1b[A\x1b[1;5D\t\x1b[99;5:3u"
        self.assertEqual(parser.feed(keys), keys)
        self.assertEqual(parser.feed(b"\x1b"), b"")
        self.assertEqual(parser.flush_escape(), b"\x1b")
        self.assertEqual(parser.feed(b"do not submit\r\x03"), b"")

    def test_footer_only_filtered_after_ui_teardown(self):
        transcript = (b"\x1b[?1049h\x1b[?2004h"
                      b"Conversation: To reconnect, run:\r\n  codex resume example\r\n"
                      b"Token usage so far: this is user text\r\n"
                      b"\x1b[?1049l\x1b[?2004l\x1b[?25h"
                      b"Disconnected from this task. Any running work continues.\r\n"
                      b"To reconnect, run:\r\n  codex --remote ws://localhost --remote-auth-token-env TOKEN resume id\r\n"
                      b"Stop the current turn: run codex --remote ws://localhost agents\r\n"
                      b"Token usage so far: total=20 input=10 output=10\r\n"
                      b"Error: unexpected failure\r\n")
        for chunk in (1, 7, len(transcript)):
            with self.subTest(chunk=chunk):
                output = bytearray()
                parser = ExitOutput(output.extend)
                for i in range(0, len(transcript), chunk):
                    parser.feed(transcript[i:i + chunk])
                parser.finish()
                plain = ANSI.sub(b"", output)
                self.assertEqual(plain, b"Conversation: To reconnect, run:\r\n  codex resume example\r\n"
                                       b"Token usage so far: this is user text\r\nError: unexpected failure\r\n")

    def test_external_editor_reentry_and_startup_errors_are_preserved(self):
        for transcript in (b"Error: unable to connect\r\n",
                           b"\x1b[?2004hUI\x1b[?2004lEDITOR\x1b[?2004hUI again\x1b[?2004l"):
            output = bytearray()
            parser = ExitOutput(output.extend)
            parser.feed(transcript)
            parser.finish()
            self.assertEqual(ANSI.sub(b"", output), ANSI.sub(b"", transcript))

    def test_external_editor_output_streams_before_reentry(self):
        output = bytearray()
        parser = ExitOutput(output.extend)
        parser.feed(b"\x1b[?2004hUI\x1b[?2004l\x1b[2J\x1b[Heditor: type here")
        self.assertIn(b"editor: type here", output)
        parser.feed(b"\r\n  new line\r\n\x1b[?2004hUI again")
        parser.finish()
        self.assertIn(b"  new line\r\n", output)


class UsageTests(unittest.TestCase):
    def test_cached_and_reasoning_counts_match_native_display(self):
        raw = {"inputTokens": 41018, "cachedInputTokens": 27264,
               "outputTokens": 792, "reasoningOutputTokens": 96}
        self.assertEqual(usage_line(raw), "Token usage so far: total=14,546 input=13,754 (+ 27,264 cached) output=792 (reasoning 96)")
        self.assertIsNone(usage_line(None))
        self.assertIsNone(usage_line({key: 0 for key in raw}))
        self.assertIsNone(normalize_usage({**raw, "cachedInputTokens": 999999}))

    def test_old_session_usage_comes_from_last_complete_token_event(self):
        usage = {"input_tokens": 20, "cached_input_tokens": 4, "output_tokens": 10, "reasoning_output_tokens": 2}
        event = {"type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": usage}}}
        data = b"\n".join([b'{"type":"other"}', json.dumps(event).encode(), b'{"type":"event_msg","payload":{"type":"token_count","info":null}}'])
        cp = {"rollouts": {"id": {"data": base64.b64encode(data).decode()}}}
        self.assertEqual(checkpoint_usage(cp, "id"), usage)
        self.assertIsNone(checkpoint_usage(cp, "missing"))


class RemovedCommandTests(unittest.TestCase):
    def test_removed_commands_are_rejected_before_starting_a_model_turn(self):
        for command in ("pause", "sync", "doctor", "check-config"):
            with self.subTest(command=command), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                parse_args([command])
        self.assertEqual(parse_args(["--", "doctor"]).prompt, "doctor")
