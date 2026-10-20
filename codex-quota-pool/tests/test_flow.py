"""Real backend and native terminal tests with local-only model responses."""
from pathlib import Path
from unittest.mock import patch
import fcntl
import json
import os
import shlex
import shutil
import struct
import tempfile
import termios
import time
import unittest
from quota_pool.cli import Config
from quota_pool.codex import Quota, alive
from quota_pool.session import Session, snapshot, write_json, PoolError
from fixtures import Provider, Terminal, HeadlessPool, fake_accounts, wait_for

@unittest.skipUnless(os.environ.get("POOL_REAL_CODEX_TEST") == "1", "set POOL_REAL_CODEX_TEST=1")
class PoolIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pool-controller-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.homes = {n: self.root / n for n in ("a", "b", "c")}
        for h in self.homes.values():
            h.mkdir()
            (h / "config.toml").write_text('model = "gpt-6-astra"\nmodel_reasoning_effort = "low"\n')
        self.config = Config(tuple(self.homes), self.homes, 10, 15, False, shutil.which("codex"))
        self.provider = Provider()
        self.addCleanup(self.provider.close)
        self.levels = {"a": 100, "b": 100, "c": 100}
        self.accounts = fake_accounts(lambda: self.levels, self.provider.args())
        self.accounts.__enter__()
        self.addCleanup(self.accounts.__exit__, None, None, None)
        self.controller = self.make_controller()
        self.addCleanup(self.controller.close)

    def query(self, config, work):
        return ({n: Quota(v, [], v == 0) for n, v in self.levels.items()}, {}, {n: "identity-" + n for n in self.levels})

    def make_controller(self):
        return HeadlessPool(self.config, self.root / "runtime")

    def apply(self):
        c = self.controller
        c.quotas, c.errors, c.identities = self.query(self.config, self.root)
        c._apply_policy()

    def test_actual_interrupt_switch_drain_and_exhausted_sync(self):
        c = self.controller
        self.provider.delay = 20
        c.create(self.root, "gpt-6-astra")
        c.start_turn("POOL_CONTROLLER_SENTINEL 继续处理这个项目，不使用工具。")
        wait_for(lambda: len(self.provider.requests) >= 1)
        self.levels["a"] = 9
        self.apply()
        self.assertEqual(c.session.state["active_account"], "b")
        wait_for(lambda: len(self.provider.requests) >= 2)
        self.levels["b"] = 9
        self.apply()
        self.assertEqual(c.session.state["active_account"], "c")
        wait_for(lambda: len(self.provider.requests) >= 3)
        backend_pid = c.backend.proc.pid
        self.levels["c"] = 9
        self.apply()
        self.assertEqual(c.session.state["status"], "draining")
        self.assertEqual(c.backend.proc.pid, backend_pid)
        self.levels["c"] = 0
        self.apply()
        self.assertIsNone(c.backend)
        self.assertEqual(c.session.state["status"], "paused_quota")
        self.assertTrue(c.session.state["resume_pending"])
        self.assertIsNone(c.session.state["pending_sync"])
        cp = c.session.load_checkpoint()
        for home in self.homes.values():
            self.assertEqual(snapshot(home, c.session.state["id"])["digest"], cp["digest"])
        self.assertIn("POOL_CONTROLLER_SENTINEL", json.dumps(self.provider.requests[-1]))
        self.assertEqual(len(self.provider.requests), 3)

    def test_natural_completion_during_switch_is_not_restarted(self):
        c = self.controller
        c.create(self.root, "gpt-6-astra")
        c.start_turn("Finish this task without tools.")
        tid = c.session.state["id"]
        wait_for(lambda: c.backend.rpc.call("thread/read", {"threadId": tid})["thread"]["status"]["type"] == "idle")
        # Deliberately leave the controller's cached active_turn stale.
        self.assertTrue(c.active_turn)
        self.levels["a"] = 9
        self.apply()
        self.assertEqual(c.session.state["active_account"], "b")
        self.assertEqual(c.session.state["status"], "idle")
        self.assertEqual(len(self.provider.requests), 1)
        c.freeze("test_end")

    def test_permissions_are_preserved_despite_different_account_defaults(self):
        extra = self.root / "extra-workspace"
        extra.mkdir()
        (self.homes["a"] / "config.toml").write_text(
            'model = "gpt-6-astra"\nsandbox_mode = "workspace-write"\napproval_policy = "on-request"\n'
            '[sandbox_workspace_write]\nnetwork_access = true\nexclude_slash_tmp = true\n'
            'exclude_tmpdir_env_var = true\nwritable_roots = [' + json.dumps(str(extra)) + ']\n')
        (self.homes["b"] / "config.toml").write_text(
            'model = "gpt-6-astra"\nsandbox_mode = "danger-full-access"\napproval_policy = "never"\n')
        c = self.controller
        c.create(self.root, "gpt-6-astra")
        original = c.session.state["settings"]
        self.assertTrue(original["sandbox"]["networkAccess"])
        c.freeze("test_switch")
        c.launch("b")
        effective = c.backend.rpc.call("thread/resume", {"threadId": c.session.state["id"], "excludeTurns": True})
        for key in ("sandbox", "approvalPolicy", "approvalsReviewer"):
            self.assertEqual(original[key], effective[key])
        self.assertEqual(len(self.provider.requests), 0)
        c.freeze("test_end")

    def test_unknown_quota_pauses_without_claiming_exhaustion(self):
        c = self.controller
        c.create(self.root, "gpt-6-astra")
        c.freeze("test_pause")
        with patch("quota_pool.codex.read_quota", side_effect=PoolError("network unavailable")):
            c.loop()
        self.assertEqual(c.session.state["status"], "paused_query")
        self.assertEqual(len(self.provider.requests), 0)

    def test_denied_account_is_not_retried_using_stale_remaining_quota(self):
        c = self.controller
        c.create(self.root, "gpt-6-astra")
        # The model service denied a turn while the quota endpoint still says 100%.
        c.quota_failed = True
        self.levels.update(b=0, c=0)
        self.apply()
        self.assertIsNone(c.backend)
        self.assertEqual(c.session.state["status"], "paused_quota")
        self.assertEqual(c.session.state["active_account"], "a")
        self.assertEqual(len(self.provider.requests), 0)

    def test_preflight_backend_reuse_and_handoff_with_real_codex(self):
        from quota_pool import codex
        controller = self.controller
        with patch.object(codex, "read_quota", wraps=codex.read_quota) as reads, \
                patch.object(codex, "Backend", wraps=codex.Backend) as created:
            controller.create(self.root, "gpt-6-astra")
            self.assertEqual([call.args[1] for call in reads.call_args_list], ["a"])
            self.assertEqual(created.call_count, 1)
            first = controller.backend
            self.assertGreater(controller.next_sync, time.monotonic())
            self.assertGreater(controller.next_query, time.monotonic())
            self.provider.delay = 20
            controller.start_turn("PREFLIGHT_CONTEXT: work without tools.")
            wait_for(lambda: len(self.provider.requests) == 1)
            self.levels["a"] = 0
            controller.quotas["a"] = Quota(0, [], True)
            controller._apply_policy()
            self.assertEqual(controller.session.state["active_account"], "b")
            self.assertEqual([call.args[1] for call in reads.call_args_list], ["a", "b"])
            self.assertEqual(created.call_count, 2)
            self.assertIsNotNone(first.proc.poll())
            wait_for(lambda: len(self.provider.requests) == 2)
            self.assertIn("PREFLIGHT_CONTEXT", json.dumps(self.provider.requests[-1]))
            controller.freeze("test_end")
            self.assertIsNone(controller.session.state["pending_sync"])
            for home in self.homes.values():
                self.assertEqual(snapshot(home, controller.session.state["id"])["digest"],
                                 controller.session.load_checkpoint()["digest"])

    def test_native_settings_survive_account_switch_without_a_model_turn(self):
        c = self.controller
        c.create(self.root, "gpt-6-astra")
        tid = c.session.state["id"]
        mode = {"mode": "plan", "settings": {"model": "gpt-6-astra", "reasoning_effort": "low",
                                                "developer_instructions": None}}
        c.backend.rpc.call("thread/settings/update", {"threadId": tid, "collaborationMode": mode,
                                                     "serviceTier": "fast"})
        original = c.backend.rpc.call("thread/resume", {"threadId": tid, "excludeTurns": True})
        c.freeze("test_switch")
        c.launch("b")
        effective = c.backend.rpc.call("thread/resume", {"threadId": tid, "excludeTurns": True})
        self.assertEqual(effective["collaborationMode"]["mode"], "plan")
        self.assertEqual(effective["serviceTier"], original["serviceTier"])
        self.assertEqual(effective["serviceTier"], "priority")  # Native normalization of /fast.
        self.assertEqual(len(self.provider.requests), 0)
        c.freeze("test_end")

    def test_launch_options_and_explicit_resume_overrides(self):
        c = self.controller
        c.overrides = {"sandbox": "read-only", "approvalPolicy": "never", "config": {"web_search": "live"}}
        c.create(self.root, "gpt-6-astra")
        self.assertEqual(c.session.state["settings"]["sandbox"]["type"], "readOnly")
        self.assertEqual(c.session.state["settings"]["approvalPolicy"], "never")
        c.freeze("test_switch")
        extra = self.root / "extra writable"
        extra.mkdir()
        other_cwd = self.root / "other project"
        other_cwd.mkdir()
        c.cwd_override = other_cwd
        c.overrides = {"sandbox": "workspace-write", "approvalPolicy": "on-request",
                       "config": {"sandbox_workspace_write": {"writable_roots": [str(extra)]}}}
        c.launch("b")
        self.assertEqual(c.session.state["settings"]["sandbox"]["type"], "workspaceWrite")
        self.assertEqual(c.session.state["settings"]["approvalPolicy"], "on-request")
        self.assertEqual(c.session.state["launch_config"]["web_search"], "live")
        self.assertEqual(c.session.state["cwd"], str(other_cwd))
        self.assertIn(str(extra), c.session.state["settings"]["sandbox"]["writableRoots"])
        c.freeze("test_switch_again")
        c.launch("c")
        self.assertEqual(c.session.state["cwd"], str(other_cwd))
        self.assertIn(str(extra), c.session.state["settings"]["sandbox"]["writableRoots"])
        c.freeze("test_end")

    def test_orphan_backend_is_stopped_before_recovery(self):
        c = self.controller
        self.provider.delay = 20
        c.create(self.root, "gpt-6-astra")
        c.start_turn("Recover this interrupted task without replaying it.")
        wait_for(lambda: len(self.provider.requests) == 1)
        previous_backend = c.backend
        # Simulate the supervisor dying: its advisory locks are released, while
        # the separate backend process remains alive.
        for lock in c.account_locks.values():
            lock.close()
        c.account_locks.clear()
        recovered = self.make_controller()
        self.addCleanup(recovered.close)
        recovered.attach(Session(c.session.directory))
        self.assertIsNotNone(previous_backend.proc.poll())
        self.assertTrue(recovered.session.state["resume_pending"])
        cp = recovered.session.load_checkpoint()
        for home in self.homes.values():
            self.assertEqual(snapshot(home, cp["root_id"])["digest"], cp["digest"])
        self.assertEqual(len(self.provider.requests), 1)
        # The abandoned controller must not persist its old manifest on cleanup.
        c.session = None


@unittest.skipUnless(os.environ.get("POOL_REAL_CODEX_TEST") == "1", "set POOL_REAL_CODEX_TEST=1")
class CdxTerminalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cdx terminal ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "project with spaces"
        self.project.mkdir()
        self.other = self.root / "another project"
        self.other.mkdir()
        self.provider = Provider()
        self.addCleanup(self.provider.close)
        self.homes = {n: self.root / n for n in ("a", "b", "c")}
        for home in self.homes.values():
            home.mkdir()
            (home / "config.toml").write_text('model = "gpt-6-astra"\nmodel_reasoning_effort = "low"\n'
                                            'sandbox_mode = "workspace-write"\napproval_policy = "on-request"\n')
        write_json(self.root / "config.json", {"accounts": list(self.homes),
                   "account_homes": {n: str(h) for n, h in self.homes.items()},
                   "poll_seconds": 1, "sync_seconds": 1, "switch_below_percent": 10,
                   "codex_binary": shutil.which("codex")})
        write_json(self.root / "provider.json", self.provider.args())
        write_json(self.root / "levels.json", {n: 100 for n in self.homes})
        self.options = ["--pool-config", str(self.root / "config.json"),
                        "--pool-runtime", str(self.root / "runtime")]

    def start(self, *args, cwd=None):
        terminal = Terminal(self.root, cwd or self.project, [*self.options, *args])
        self.addCleanup(terminal.close)
        return terminal

    def session(self):
        return Session(next((self.root / "runtime").glob("*/state.json")).parent)

    def assert_closed(self, terminal, tid, status="paused_user"):
        self.assertIn(terminal.proc.returncode, (0, 130), bytes(terminal.output[-5000:]))
        state = self.session().state
        self.assertEqual(state["id"], tid)
        self.assertEqual(state["status"], status)
        self.assertIsNone(state["backend"])
        self.assertIsNone(state["tui"])
        self.assertIsNone(state["controller"])
        self.assertIsNone(state["pending_sync"])
        expected = shlex.join(["cdx", *self.options, "resume", tid])
        self.assertIn(expected.encode(), terminal.output)
        self.assertEqual(terminal.output.count(b"To reconnect, run:"), 1)
        for hidden in (b"--remote", b"CODEX_POOL_BACKEND_TOKEN", b"Disconnected from this task.",
                       b"Stop the current turn:", "额度池会话".encode(), "所有副本同步到".encode(),
                       "会话已保存。继续使用额度池".encode()):
            self.assertNotIn(hidden, terminal.output)
        self.assertTrue(termios.tcgetattr(terminal.master)[3] & termios.ICANON)
        self.assertTrue(termios.tcgetattr(terminal.master)[3] & termios.ECHO)
        cp = self.session().load_checkpoint()
        for home in self.homes.values():
            self.assertEqual(snapshot(home, tid)["digest"], cp["digest"])

    def test_start_ctrl_c_and_resume_from_another_directory(self):
        terminal = self.start("-m", "gpt-6-astra", "--no-alt-screen", "CDX_SENTINEL: no tools please.")
        terminal.until(lambda: b"CHECKPOINT_1" in terminal.output)
        session = self.session()
        tid = session.state["id"]
        self.assertEqual(session.state["cwd"], str(self.project))
        backend = session.state["backend"]
        terminal.exit()
        self.assert_closed(terminal, tid)
        self.assertFalse(alive(backend))
        self.assertIn(b"Token usage so far: total=20 input=10 output=10", terminal.output)
        resumed = self.start("resume", tid, cwd=self.other)
        resumed.until(lambda: b"CHECKPOINT_1" in resumed.output)
        self.assertEqual(self.session().state["cwd"], str(self.project))
        self.assertEqual(len(self.provider.requests), 1)
        resumed.send(b"Continue CDX_SENTINEL without tools.")
        resumed.pump(.3)  # End the native terminal's paste-burst detection window.
        resumed.send(b"\r")
        resumed.until(lambda: b"CHECKPOINT_2" in resumed.output)
        self.assertIn("CDX_SENTINEL", json.dumps(self.provider.requests[-1]))
        resumed.send(b"/plan")
        resumed.pump(.3)
        resumed.send(b"\r")
        resumed.pump(.8)
        resumed.exit()
        self.assert_closed(resumed, tid)
        self.assertEqual(self.session().state["settings"]["collaborationMode"]["mode"], "plan")
        self.assertIn(b"Token usage so far: total=40 input=20 output=20", resumed.output)

    def test_ctrl_c_during_work_does_not_restart_on_resume(self):
        self.provider.delay = 20
        terminal = self.start("CDX_INTERRUPTED: work without tools.")
        terminal.until(lambda: len(self.provider.requests) == 1)
        tid = self.session().state["id"]
        backend = self.session().state["backend"]
        terminal.exit()
        self.assert_closed(terminal, tid)
        self.assertFalse(alive(backend))
        self.assertNotIn(b"Token usage so far:", terminal.output)
        resumed = self.start("resume", "--last")
        resumed.until(lambda: self.session().state.get("tui") and self.session().state["status"] == "idle")
        resumed.pump(1)
        self.assertEqual(len(self.provider.requests), 1)
        resumed.exit()
        self.assert_closed(resumed, tid)

    def test_slash_quit_has_one_valid_footer_and_cached_usage(self):
        self.provider.cached_tokens = 4
        self.provider.reasoning_tokens = 3
        terminal = self.start("CDX_QUIT: no tools please.")
        terminal.until(lambda: b"CHECKPOINT_1" in terminal.output)
        tid = self.session().state["id"]
        terminal.send(b"/quit")
        terminal.pump(.3)
        terminal.send(b"\r")
        terminal.until(lambda: terminal.proc.poll() is not None)
        terminal.pump()
        self.assert_closed(terminal, tid)
        self.assertEqual(terminal.output.count(b"Token usage so far:"), 1)
        self.assertIn(b"total=16 input=6 (+ 4 cached) output=10 (reasoning 3)", terminal.output)

    def test_paste_resize_and_enhanced_ctrl_c(self):
        terminal = self.start()
        terminal.until(lambda: b"\x1b[?2004h" in terminal.output)
        terminal.send(b"\x1b[200~literal \x03 paste\x1b[201~")
        terminal.pump(.5)
        self.assertIsNone(terminal.proc.poll())
        self.assertEqual(self.provider.requests, [])
        fcntl.ioctl(terminal.master, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 100, 0, 0))
        terminal.pump(.2)
        tui_pid = self.session().state["tui"]["pid"]
        fd = os.open(f"/proc/{tui_pid}/fd/0", os.O_RDONLY | os.O_NOCTTY)
        try:
            size = fcntl.ioctl(fd, termios.TIOCGWINSZ, b"\0" * 8)
        finally:
            os.close(fd)
        self.assertEqual(struct.unpack("HHHH", size)[:2], (40, 100))
        terminal.send(b"\x1b[99;5u")
        terminal.until(lambda: terminal.proc.poll() is not None)
        terminal.pump()
        self.assert_closed(terminal, self.session().state["id"])

    def test_handoffs_hide_intermediate_footers_and_exhaustion_still_explains_pause(self):
        self.provider.delay = 25
        terminal = self.start("CDX_HANDOFF: work without tools.")
        terminal.until(lambda: len(self.provider.requests) == 1)
        levels = {n: 100 for n in self.homes}
        for count, account in ((2, "a"), (3, "b")):
            levels[account] = 9
            write_json(self.root / "levels.json", levels)
            terminal.until(lambda: len(self.provider.requests) == count)
            self.assertNotIn(b"To reconnect, run:", terminal.output)
            self.assertNotIn(b"--remote", terminal.output)
        levels["c"] = 0
        write_json(self.root / "levels.json", levels)
        terminal.until(lambda: terminal.proc.poll() is not None)
        terminal.pump()
        self.assert_closed(terminal, self.session().state["id"], status="paused_quota")
        self.assertIn("额度已耗尽，任务已暂停。".encode(), terminal.output)
        self.assertEqual(self.session().state["active_account"], "c")
        self.assertEqual(self.session().state["settings"]["approvalPolicy"], "on-request")
        self.assertEqual(self.session().state["settings"]["sandbox"]["type"], "workspaceWrite")
        self.assertIn("CDX_HANDOFF", json.dumps(self.provider.requests[-1]))
