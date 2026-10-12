import contextlib
import datetime as dt
import io
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

import quota_watch as q


def at(value):
    return dt.datetime.fromisoformat(value).replace(tzinfo=q.TZ).timestamp()


class FakeGateway:
    def __init__(self, quota):
        self.quota = quota
        self.queries = 0
        self.tasks = 0
        self.query_error = None
        self.task_error = None
        self.on_task = None

    def query(self, timeout):
        self.queries += 1
        if self.query_error:
            raise self.query_error
        return self.quota

    def task(self, timeout):
        self.tasks += 1
        if self.on_task:
            self.on_task(timeout)
        if self.task_error:
            raise self.task_error
        return "example.txt"


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.now = at("2026-10-11T08:00:00")
        self.config = {"query_timeout_seconds": 30, "task_timeout_seconds": 120,
                       "retry_seconds": 300, "settle_seconds": 60,
                       "max_attempts_per_window": 3}
        self.stop = threading.Event()
        self.gateway = FakeGateway(q.Quota(0, self.now + 18000, "account-identity"))
        self.runner = self.make_runner()

    def make_runner(self, name="account-1", gateway=None):
        return q.Runner(self.root, name, self.config, gateway or self.gateway, self.stop, lambda: self.now)

    def advance_to_due(self):
        self.now = self.runner.state["next_check"]

    def test_day_boundaries(self):
        for timestamp, working in [("07:59:59", False), ("08:00:00", True),
                                   ("21:59:59", True), ("22:00:00", False)]:
            with self.subTest(timestamp=timestamp):
                self.assertEqual(q.working(at("2026-10-11T" + timestamp)), working)
        self.assertEqual(q.next_work_time(at("2026-10-11T22:00:00")), at("2026-10-12T08:00:00"))

    def test_night_never_queries_or_tasks(self):
        self.now = at("2026-10-11T23:00:00")
        self.runner.tick()
        self.assertEqual((self.gateway.queries, self.gateway.tasks), (0, 0))
        self.assertEqual(self.runner.state["next_check"], at("2026-10-12T08:00:00"))

    def test_full_quota_task_then_verify_and_wait_for_server_reset(self):
        self.runner.tick()
        self.assertEqual(self.gateway.tasks, 1)
        self.assertEqual(self.runner.state["next_check"], self.now + 60)
        self.gateway.quota.used = 1
        self.advance_to_due()
        self.runner.tick()
        self.assertEqual(self.gateway.tasks, 1)
        self.assertEqual(self.runner.state["next_check"], self.gateway.quota.reset + 60)

    def test_network_outage_retries_every_five_minutes_without_tasks(self):
        self.gateway.query_error = q.WatchError("代理未连接")
        self.runner.tick()
        self.assertEqual(self.runner.state["next_check"], self.now + 300)
        self.now += 30
        self.runner.tick()
        self.assertEqual(self.gateway.queries, 1)
        self.advance_to_due()
        self.runner.tick()
        self.assertEqual(self.runner.state["consecutive_failures"], 2)
        self.assertEqual(self.gateway.tasks, 0)
        self.gateway.query_error = None
        self.gateway.quota.used = 20
        self.advance_to_due()
        self.runner.tick()
        self.assertEqual(self.runner.state["consecutive_failures"], 0)
        self.assertEqual(self.gateway.tasks, 0)
        self.assertEqual(self.runner.state["next_check"], self.gateway.quota.reset + 60)

    def test_night_retry_waits_until_morning(self):
        self.now = at("2026-10-11T21:58:00")
        self.gateway.query_error = q.WatchError("网络错误")
        self.runner.tick()
        self.assertEqual(self.runner.state["next_check"], at("2026-10-12T08:00:00"))

    def test_reset_after_work_hours_waits_until_morning(self):
        self.gateway.quota = q.Quota(12, at("2026-10-11T23:00:00"), "account-identity")
        self.runner.tick()
        self.assertEqual(self.gateway.tasks, 0)
        self.assertEqual(self.runner.state["next_check"], at("2026-10-12T08:00:00"))

    def test_three_attempt_limit_survives_restarts_and_reset_timestamp_drift(self):
        for _ in range(3):
            self.runner.tick()
            self.advance_to_due()
            self.gateway.quota.reset += 7
            self.runner = self.make_runner()
        self.runner.tick()
        self.assertEqual(self.gateway.tasks, 3)
        self.assertIn("上限", self.runner.state["status"])
        self.assertEqual(self.runner.state["next_check"], self.gateway.quota.reset + 60)

    def test_next_window_can_run_again(self):
        for _ in range(3):
            self.runner.tick()
            self.advance_to_due()
        self.runner.tick()
        self.advance_to_due()
        self.gateway.quota.reset = self.now + 18000
        self.runner.tick()
        self.assertEqual(self.gateway.tasks, 4)
        self.assertEqual(self.runner.state["attempts"], 1)

    def test_missing_reset_is_bounded_and_waits_for_authoritative_time(self):
        self.gateway.quota.reset = None
        for _ in range(3):
            self.runner.tick()
            self.advance_to_due()
        self.runner.tick()
        self.assertEqual(self.gateway.tasks, 3)
        self.assertGreater(self.runner.state["next_check"], self.now + 3600)

    def test_nonfull_without_reset_polls_without_consumption(self):
        self.gateway.quota = q.Quota(5, None, "account-identity")
        self.runner.tick()
        self.assertEqual(self.gateway.tasks, 0)
        self.assertEqual(self.runner.state["next_check"], self.now + 300)

    def test_unknown_task_result_is_counted_and_rechecked_after_retry(self):
        self.gateway.task_error = q.WatchError("任务断网，结果不确定")
        self.runner.tick()
        saved = q.read_json(self.runner.path)
        self.assertEqual(saved["attempts"], 1)
        self.assertTrue(saved["inflight"])
        self.assertEqual(saved["next_check"], self.now + 300)
        self.runner = self.make_runner()
        self.gateway.quota.used = 1
        self.advance_to_due()
        self.runner.tick()
        self.assertEqual(self.gateway.tasks, 1)

    def test_attempt_saved_before_task_starts_and_stopping_preserves_it(self):
        def inspect(timeout):
            saved = q.read_json(self.runner.path)
            self.assertEqual(saved["attempts"], 1)
            self.assertTrue(saved["inflight"])
            raise q.Cancelled("停止")
        self.gateway.on_task = inspect
        with self.assertRaises(q.Cancelled):
            self.runner.tick()
        self.assertEqual(q.read_json(self.runner.path)["attempts"], 1)

    def test_accounts_do_not_share_retry_or_attempt_state(self):
        other = FakeGateway(q.Quota(0, self.now + 18000, "other"))
        runner2 = self.make_runner("account-2", other)
        self.gateway.query_error = q.WatchError("账号一网络异常")
        self.runner.tick()
        runner2.tick()
        self.assertEqual(other.tasks, 1)
        self.assertEqual(self.gateway.tasks, 0)
        self.assertEqual(self.runner.state["next_check"], self.now + 300)
        self.assertEqual(runner2.state["next_check"], self.now + 60)

    def test_changed_login_identity_stops_without_a_task(self):
        self.gateway.quota.used = 10
        self.runner.tick()
        self.advance_to_due()
        self.gateway.quota = q.Quota(0, self.now + 18000, "different-account")
        with self.assertRaises(q.WatchError):
            self.runner.tick()
        self.assertEqual(self.gateway.tasks, 0)

    def test_task_timeout_cannot_cross_2200(self):
        self.now = at("2026-10-11T21:59:40")
        self.gateway.quota.reset = self.now + 18000
        self.gateway.on_task = lambda timeout: self.assertEqual(timeout, 20)
        self.runner.tick()
        self.assertEqual(self.runner.state["next_check"], at("2026-10-12T08:00:00"))

    def test_late_query_cannot_start_night_task(self):
        def late_query(timeout):
            self.now = at("2026-10-11T22:00:01")
            return self.gateway.quota
        self.gateway.query = late_query
        self.runner.tick()
        self.assertEqual(self.gateway.tasks, 0)

    def test_corrupt_state_fails_closed(self):
        self.runner.path.parent.mkdir(parents=True)
        self.runner.path.write_text("invalid json")
        with self.assertRaises(q.WatchError):
            self.make_runner()

    def test_invalid_state_shape_and_counter_fail_closed(self):
        for value in ([], {"attempts": "0"}, {"attempts": -1}, {"next_check": None}):
            q.write_json(self.runner.path, value)
            with self.subTest(value=value), self.assertRaises(q.WatchError):
                self.make_runner()

    def test_resume_displays_waiting_without_bypassing_next_check(self):
        self.gateway.quota.used = 100
        self.runner.tick()
        due = self.runner.state["next_check"]
        self.runner.state["status"] = "已手动停止"
        self.runner.save()
        self.runner = self.make_runner()
        with patch.object(self.runner, "tick", side_effect=lambda: self.stop.set()):
            with patch.object(self.runner, "save") as save:
                saved_statuses = []
                save.side_effect = lambda: saved_statuses.append(self.runner.state["status"])
                self.runner.run()
        self.assertEqual(saved_statuses[0], "等待额度刷新")
        self.assertEqual(self.runner.state["next_check"], due)
        self.assertEqual(self.gateway.tasks, 0)


class QuotaParsingTests(unittest.TestCase):
    def snapshot(self, used=0, reset=1791700000):
        return {"rateLimits": {"limitId": "codex", "primary": {"windowDurationMins": 10080, "usedPercent": 95},
                               "secondary": {"windowDurationMins": 300, "usedPercent": used, "resetsAt": reset}}}

    def test_selects_five_hour_window_even_when_secondary(self):
        self.assertEqual(q.parse_quota(self.snapshot(), "a").used, 0)

    def test_multi_bucket_view_is_authoritative(self):
        data = self.snapshot()
        data["rateLimitsByLimitId"] = {"other": data["rateLimits"]}
        with self.assertRaises(q.WatchError):
            q.parse_quota(data, "a")

    def test_missing_or_invalid_data_is_not_full_quota(self):
        for used in (None, "0", True, -1, 101, float("nan"), float("inf")):
            with self.subTest(used=used), self.assertRaises(q.WatchError):
                q.parse_quota(self.snapshot(used), "a")

    def test_weekly_window_alone_is_rejected(self):
        data = self.snapshot()
        del data["rateLimits"]["secondary"]
        with self.assertRaises(q.WatchError):
            q.parse_quota(data, "a")


class ProcessTests(unittest.TestCase):
    def test_rpc_handles_notifications_and_chunked_replies(self):
        script = r'''
import sys,json,time
for line in sys.stdin:
 r=json.loads(line)
 if "id" not in r: continue
 print(json.dumps({"method":"noise","params":{}}),flush=True)
 payload=json.dumps({"id":r["id"],"result":{"ok":True}})+"\n"
 sys.stdout.write(payload[:5]);sys.stdout.flush()
 time.sleep(.005)
 sys.stdout.write(payload[5:]);sys.stdout.flush()
'''
        import os
        with q.AppServer([sys.executable, "-u", "-c", script], dict(os.environ), "/tmp", 3, threading.Event()) as server:
            self.assertEqual(server.call("account/read"), {"ok": True})
        self.assertIsNotNone(server.proc.poll())

    def test_hung_server_times_out_and_is_terminated(self):
        import os
        with self.assertRaises(q.WatchError):
            with q.AppServer([sys.executable, "-c", "import time; time.sleep(10)"],
                             dict(os.environ), "/tmp", .05, threading.Event()):
                pass

    def test_duplicate_runner_lock_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "test.lock"
            with q.exclusive(path):
                with self.assertRaises(q.WatchError):
                    with q.exclusive(path):
                        pass

    def test_task_subprocess_writes_output_and_returns_without_hanging(self):
        import os
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            binary = root / "fake-codex"
            binary.write_text('#!' + sys.executable + '\n' +
                'import pathlib,sys\n'
                'assert sys.argv[1] == "exec"\n'
                'assert sys.argv[sys.argv.index("--sandbox") + 1] == "read-only"\n'
                'pathlib.Path(sys.argv[sys.argv.index("--output-last-message") + 1]).write_text("test output")\n')
            binary.chmod(0o700)
            config = {"codex_binary": str(binary), "accounts": {"test": {"home": str(root), "model": "example"}}}
            gateway = q.CodexGateway(config, "test", root, threading.Event())
            output = gateway.task(3)
            self.assertEqual((root/"runtime/test/outputs"/output).read_text(), "test output")

    def test_cancelled_task_terminates_its_process(self):
        import os
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            binary = root / "fake-codex"
            binary.write_text('#!' + sys.executable + '\nimport time\ntime.sleep(30)\n')
            binary.chmod(0o700)
            config = {"codex_binary": str(binary), "accounts": {"test": {"home": str(root), "model": "example"}}}
            stop = threading.Event()
            stop.set()
            gateway = q.CodexGateway(config, "test", root, stop)
            with self.assertRaises(q.Cancelled):
                gateway.task(3)


class ManagementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = {"query_timeout_seconds": 30, "task_timeout_seconds": 120,
                       "retry_seconds": 300, "settle_seconds": 60,
                       "max_attempts_per_window": 3,
                       "accounts": {"one": {"home": "/tmp/one", "model": "example"},
                                    "two": {"home": "/tmp/two", "model": "example"}}}
        q.write_json(self.root / "config.json", self.config)

    def call(self, *args):
        return q.main(["--root", str(self.root), *args])

    @patch.object(q, "systemctl")
    def test_start_multiple_accounts(self, ctl):
        self.call("start", "one", "two")
        ctl.assert_called_once_with("enable", "--now", "codex-quota@one.service", "codex-quota@two.service")

    @patch.object(q, "systemctl")
    def test_stop_one_preserves_other_account_and_attempt_budget(self, ctl):
        for name in ("one", "two"):
            q.write_json(self.root / "runtime" / name / "state.json", {"attempts": 2, "status": "等待刷新"})
        self.call("stop", "one")
        ctl.assert_called_once_with("disable", "--now", "codex-quota@one.service")
        self.assertEqual(q.read_json(self.root / "runtime/one/state.json")["attempts"], 2)
        self.assertEqual(q.read_json(self.root / "runtime/two/state.json")["status"], "等待刷新")

    @patch.object(q, "systemctl")
    def test_stop_all_targets_every_registered_account(self, ctl):
        self.call("stop", "--all")
        ctl.assert_called_once_with("disable", "--now", "codex-quota@one.service", "codex-quota@two.service")

    @patch.object(q, "systemctl")
    def test_unknown_name_changes_no_services(self, ctl):
        with self.assertRaises(q.WatchError):
            self.call("start", "one", "unknown")
        ctl.assert_not_called()


class DisplayQueryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.now = at("2026-10-11T10:00:00")
        self.config = {"codex_binary": "unused-test-binary", "query_timeout_seconds": 30,
                       "task_timeout_seconds": 120, "retry_seconds": 300,
                       "settle_seconds": 60, "max_attempts_per_window": 3,
                       "accounts": {"one": {"home": str(self.root / "one"), "model": "example"},
                                    "two": {"home": str(self.root / "two"), "model": "example"}}}
        q.write_json(self.root / "config.json", self.config)
        self.state = {"last_quota": {"remaining_percent": 90, "resets_at": self.now + 18000},
                      "last_success": self.now - 600, "next_check": self.now + 18060,
                      "attempts": 1, "budget_until": self.now + 18000, "status": "等待刷新"}
        self.state_path = self.root / "runtime/one/state.json"
        q.write_json(self.state_path, self.state)
        self.ctl = patch.object(q, "systemctl", return_value=subprocess.CompletedProcess([], 0, "active\n", "")).start()
        self.addCleanup(patch.stopall)
        patch.object(q.time, "time", return_value=self.now).start()
        self.task = patch.object(q.CodexGateway, "task", side_effect=AssertionError("display must never run model tasks")).start()

    def call(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = q.main(["--root", str(self.root), *args])
        self.task.assert_not_called()
        return code, output.getvalue()

    def fresh(self):
        return patch.object(q.CodexGateway, "query", return_value=q.Quota(39, self.now + 15456, "account"))

    def test_status_uses_live_quota_and_preserves_scheduler_file(self):
        before = self.state_path.read_bytes()
        with self.fresh() as query:
            code, output = self.call("status", "one")
        self.assertEqual(code, 0)
        self.assertEqual(query.call_count, 1)
        self.assertIn("61%", output)
        self.assertNotIn("90%", output)
        self.assertIn("4h 17m 36s", output)
        self.assertIn("实时", output)
        self.assertIn("本次查询时间", output)
        self.assertIn(q.formatted(self.now), output)
        self.assertEqual(self.state_path.read_bytes(), before)

    def test_check_has_the_same_human_format_as_status(self):
        with self.fresh():
            check_code, check = self.call("check", "one")
            status_code, status = self.call("status", "one")
        self.assertEqual(check_code, status_code)
        self.assertEqual(check, status)
        self.assertTrue(check.startswith("one · 监测中"))

    def test_check_json_keeps_existing_fields_and_adds_source(self):
        with self.fresh():
            code, output = self.call("check", "one", "--json")
        data = json.loads(output)
        self.assertEqual(code, 0)
        self.assertEqual(data["account"], "one")
        self.assertEqual(data["remaining_percent"], 61)
        self.assertEqual(data["seconds_until_reset"], 15456)
        self.assertEqual(data["time_until_reset"], "4h 17m 36s")
        self.assertEqual(data["resets_at"], self.now + 15456)
        self.assertEqual(data["source"], "live")
        self.assertTrue(data["query_ok"])

    def test_cached_status_and_list_do_not_call_codex(self):
        with patch.object(q, "CodexGateway") as gateway:
            for args in (("status", "one", "--cached"), ("list",)):
                with self.subTest(args=args):
                    code, output = self.call(*args)
                    self.assertEqual(code, 0)
                    self.assertIn("90%", output)
                    self.assertIn("缓存（非实时）", output)
                    self.assertIn("缓存采样时间", output)
                    self.assertIn(q.formatted(self.now - 600), output)
            gateway.assert_not_called()

    def test_all_accounts_query_concurrently_and_one_failure_is_isolated(self):
        barrier = threading.Barrier(2, timeout=3)
        def query(gateway, timeout):
            barrier.wait()
            if gateway.name == "one":
                raise q.WatchError("代理不可用")
            return q.Quota(25, self.now + 3600, "second")
        with patch.object(q.CodexGateway, "query", autospec=True, side_effect=query):
            code, output = self.call("status", "--all", "--json")
        reports = json.loads(output)
        self.assertEqual(code, 1)
        self.assertEqual([r["account"] for r in reports], ["one", "two"])
        self.assertEqual(reports[0]["source"], "cache")
        self.assertEqual(reports[0]["remaining_percent"], 90)
        self.assertFalse(reports[0]["query_ok"])
        self.assertEqual(reports[1]["source"], "live")
        self.assertEqual(reports[1]["remaining_percent"], 75)
        self.assertTrue(reports[1]["query_ok"])

    def test_query_failure_marks_cached_data_and_preserves_its_age(self):
        with patch.object(q.CodexGateway, "query", side_effect=q.WatchError("额度查询超时")):
            code, output = self.call("check", "one")
        self.assertEqual(code, 1)
        self.assertIn("实时查询失败", output)
        self.assertIn("缓存（非实时）", output)
        self.assertIn(q.formatted(self.now - 600), output)
        self.assertNotIn("本次查询时间", output)

    def test_failure_without_cache_displays_unknown_instead_of_zero_or_full(self):
        with patch.object(q.CodexGateway, "query", side_effect=q.WatchError("断网")):
            code, output = self.call("check", "two")
        self.assertEqual(code, 1)
        self.assertIn("暂无数据", output)
        self.assertIn("未知", output)
        self.assertNotIn("0%", output)

    def test_expired_cache_warns_that_reset_time_has_passed(self):
        self.state["last_quota"]["resets_at"] = self.now - 1
        q.write_json(self.state_path, self.state)
        code, output = self.call("status", "one", "--cached")
        self.assertEqual(code, 0)
        self.assertIn("0h 0m 0s", output)
        self.assertIn("缓存中的刷新时间已过", output)

    def test_stopped_monitor_can_query_live_without_restarting(self):
        self.ctl.return_value = subprocess.CompletedProcess([], 3, "inactive\n", "")
        with self.fresh():
            code, output = self.call("check", "one")
        self.assertEqual(code, 0)
        self.assertIn("one · 已停止", output)
        self.assertIn("61%", output)
        self.assertIn("—（未运行）", output)
        self.assertTrue(all(call.args[0] == "is-active" for call in self.ctl.call_args_list))

    def test_missing_systemd_does_not_block_live_quota(self):
        self.ctl.side_effect = OSError("no bus")
        with self.fresh():
            code, output = self.call("check", "one")
        self.assertEqual(code, 0)
        self.assertIn("监测状态未知", output)
        self.assertIn("61%", output)

    def test_corrupt_scheduler_state_does_not_block_live_quota_or_get_overwritten(self):
        self.state_path.write_text("broken json")
        with self.fresh():
            code, output = self.call("check", "one")
        self.assertEqual(code, 0)
        self.assertIn("61%", output)
        self.assertEqual(self.state_path.read_text(), "broken json")

    def test_json_cache_and_unknown_reset_keep_null_seconds(self):
        self.state["last_quota"]["resets_at"] = None
        q.write_json(self.state_path, self.state)
        code, output = self.call("list", "--json")
        report = json.loads(output)[0]
        self.assertEqual(code, 0)
        self.assertEqual(report["source"], "cache")
        self.assertIsNone(report["seconds_until_reset"])
        self.assertEqual(report["time_until_reset"], "未知")


if __name__ == "__main__":
    unittest.main()
