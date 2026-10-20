"""Checkpoint integrity, recovery and real Codex roundtrips."""
from pathlib import Path
from unittest.mock import patch
import contextlib
import json
import os
import shutil
import sqlite3
import tempfile
import time
import unittest
from quota_pool.cli import Config
from quota_pool.session import Lock, PoolError, Session, Syncer, connect, initialize_db, install, snapshot
from quota_pool.codex import Backend, Rpc
from fixtures import Provider, fixture, advance

class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pool-storage-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.homes = {n: self.root / n for n in ("a", "b", "c")}
        self.tid = fixture(self.homes["a"])
        self.unrelated = {}
        for n in ("b", "c"):
            self.unrelated[n] = fixture(self.homes[n])
            (self.homes[n] / "auth.json").write_text("credential-marker-" + n)
        self.session = Session.create(self.root / "runtime", self.tid, "a", self.homes, self.root, {})
        self.sync = Syncer(self.session)

    def test_replication_leaves_unrelated_threads_and_credentials(self):
        before = {n: snapshot(self.homes[n], tid)["digest"] for n, tid in self.unrelated.items()}
        self.sync.sync(self.homes, frozen=True)
        for n in ("b", "c"):
            self.assertEqual(snapshot(self.homes[n], self.tid)["digest"], self.session.load_checkpoint()["digest"])
            self.assertEqual(snapshot(self.homes[n], self.unrelated[n])["digest"], before[n])
            self.assertEqual((self.homes[n] / "auth.json").read_text(), "credential-marker-" + n)

    def test_repair_partial_installation_then_capture_new_progress(self):
        self.sync.sync(self.homes)
        advance(self.homes["a"], self.tid, "CHECKPOINT_2")
        original = install

        def fail_on_second_target(home, cp):
            if home == self.homes["c"]:
                # Simulate a crash after the file write and before SQLite commit.
                import base64
                r = cp["rollouts"][self.tid]
                (home / r["relative"]).write_bytes(base64.b64decode(r["data"]))
                raise OSError("simulated power loss")
            original(home, cp)

        with patch("quota_pool.session.install", side_effect=fail_on_second_target), self.assertRaises(OSError):
            self.sync.sync(self.homes)
        self.assertIsNotNone(self.session.state["pending_sync"])
        advance(self.homes["a"], self.tid, "CHECKPOINT_3_BEFORE_FREEZE")
        recovered = Session(self.session.directory)
        Syncer(recovered).sync(self.homes)
        Syncer(recovered).sync(self.homes, frozen=True)
        self.assertIsNone(recovered.state["pending_sync"])
        for home in self.homes.values():
            cp = snapshot(home, self.tid)
            self.assertEqual(cp["digest"], recovered.load_checkpoint()["digest"])
            self.assertIn("CHECKPOINT_3_BEFORE_FREEZE", (home / cp["rollouts"][self.tid]["relative"]).read_text())

    def test_diverged_replica_is_never_overwritten(self):
        self.sync.sync(self.homes)
        advance(self.homes["b"], self.tid, "INDEPENDENT_EDIT")
        before = snapshot(self.homes["b"], self.tid)["digest"]
        advance(self.homes["a"], self.tid, "AUTHORITATIVE_EDIT")
        with self.assertRaisesRegex(PoolError, "覆盖"):
            self.sync.sync(self.homes)
        self.assertEqual(snapshot(self.homes["b"], self.tid)["digest"], before)

    def test_loaded_target_refuses_sync(self):
        self.sync.sync(self.homes)
        advance(self.homes["a"], self.tid, "NEW")
        with Lock(self.homes["b"] / "thread-writer-locks" / (self.tid + ".lock")):
            with self.assertRaisesRegex(PoolError, "正在使用"):
                self.sync.sync(self.homes)

    def test_tampered_checkpoint_fails_verification(self):
        self.sync.sync(self.homes)
        import gzip
        path = self.session.directory / self.session.state["checkpoint"]
        data = json.loads(gzip.decompress(path.read_bytes()))
        data["digest"] = "wrong"
        path.write_bytes(gzip.compress(json.dumps(data).encode()))
        with self.assertRaisesRegex(PoolError, "校验失败"):
            self.session.load_checkpoint()

    def test_partial_final_line_is_not_copied(self):
        advance(self.homes["a"], self.tid, "COMPLETE")
        path = self.homes["a"] / "sessions" / f"rollout-{self.tid}.jsonl"
        with path.open("ab") as f:
            f.write(b'{"type":"partial')
        self.sync.sync(self.homes)
        target = self.homes["b"] / "sessions" / path.name
        self.assertTrue(target.read_bytes().endswith(b"\n"))
        self.assertNotIn(b'"partial', target.read_bytes())

    def test_unknown_version_is_refused(self):
        with contextlib.closing(sqlite3.connect(self.homes["a"] / "state_5.sqlite")) as db, db:
            db.execute("UPDATE threads SET cli_version='0.999.0'")
        with self.assertRaisesRegex(PoolError, "版本"):
            self.sync.sync(self.homes)

    def test_index_rebuild_does_not_invalidate_existing_checkpoint(self):
        for home in self.homes.values():
            with contextlib.closing(sqlite3.connect(home / "state_5.sqlite")) as db, db:
                db.execute("ALTER TABLE threads ADD COLUMN updated_at_ms INTEGER")
                db.execute("ALTER TABLE threads ADD COLUMN created_at_ms INTEGER")
                db.execute("UPDATE threads SET updated_at_ms = 1700000000123")
                db.execute("UPDATE threads SET created_at_ms = 1700000000000")
        self.sync.sync(self.homes)
        checkpoint = self.session.load_checkpoint()
        for name in ("b", "c"):
            with contextlib.closing(sqlite3.connect(self.homes[name] / "state_5.sqlite")) as db, db:
                db.execute("UPDATE threads SET updated_at_ms = updated_at_ms + 1234 WHERE id=?", (self.tid,))
                db.execute("UPDATE threads SET created_at_ms = created_at_ms + 1 WHERE id=?", (self.tid,))
        advance(self.homes["a"], self.tid, "AFTER_ACCOUNT_QUERY")
        with contextlib.closing(sqlite3.connect(self.homes["a"] / "state_5.sqlite")) as db, db:
            db.execute("UPDATE threads SET updated_at_ms = updated_at_ms + 5678 WHERE id=?", (self.tid,))
        self.sync.sync(self.homes)
        self.assertEqual(checkpoint["format"], 1)
        for home in self.homes.values():
            self.assertEqual(snapshot(home, self.tid)["digest"], self.session.load_checkpoint()["digest"])

    def test_index_rebuild_does_not_hide_other_database_edits(self):
        self.sync.sync(self.homes)
        with contextlib.closing(sqlite3.connect(self.homes["b"] / "state_5.sqlite")) as db, db:
            db.execute("UPDATE threads SET cwd='/independent-edit' WHERE id=?", (self.tid,))
        before = snapshot(self.homes["b"], self.tid)
        with self.assertRaisesRegex(PoolError, "覆盖"):
            self.sync.sync(self.homes)
        self.assertEqual(snapshot(self.homes["b"], self.tid), before)

    def test_snapshot_connection_forbids_sql_writes(self):
        with contextlib.closing(connect(self.homes["a"] / "state_5.sqlite")) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM threads").fetchone()[0], 1)
            with self.assertRaises(sqlite3.OperationalError):
                db.execute("DELETE FROM threads")

    def test_schema_failure_does_not_publish_partial_database(self):
        checkpoint = snapshot(self.homes["a"], self.tid)
        schema = checkpoint["schemas"]["state_5.sqlite"]
        broken = {**schema, "definitions": [*schema["definitions"],
                                           {"type": "table", "sql": "INVALID SQL"}]}
        path = self.root / "new.sqlite"
        with self.assertRaises(sqlite3.Error):
            initialize_db(path, broken)
        self.assertFalse(path.exists())
        self.assertEqual(list(self.root.glob('.pool-schema-*')), [])
        initialize_db(path, schema)
        with contextlib.closing(sqlite3.connect(path)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM _sqlx_migrations').fetchone()[0], 1)
        # Existing databases are retained, even if a different schema is offered.
        initialize_db(path, broken)


def turn(rpc, tid, text):
    rpc.call("turn/start", {"threadId": tid, "input": [{"type": "text", "text": text}], "effort": "low"})
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        for event in rpc.drain():
            if event.get("method") == "turn/completed" and event["params"]["threadId"] == tid:
                status = event["params"]["turn"]["status"]
                if status != "completed":
                    raise AssertionError(event)
                return
        time.sleep(.05)
    raise AssertionError("turn did not complete")


@unittest.skipUnless(os.environ.get("POOL_REAL_CODEX_TEST") == "1", "set POOL_REAL_CODEX_TEST=1")
class RealCodexTests(unittest.TestCase):
    def test_three_homes_roundtrip_context_and_pagination(self):
        with tempfile.TemporaryDirectory(prefix="pool-real-") as tmp, Provider() as provider:
            root = Path(tmp)
            homes = {name: root / name for name in ("a", "b", "c")}
            for home in homes.values():
                home.mkdir()
            config = Config(tuple(homes), homes, 10, 15, False, shutil.which("codex"))

            def open_server(name):
                return Rpc([config.binary, "app-server", "--listen", "stdio://", *provider.args()],
                           config.env(name), root, timeout=20)

            with open_server("a") as rpc:
                result = rpc.call("thread/start", {"cwd": str(root), "model": "gpt-6-astra", "sandbox": "read-only",
                                                   "approvalPolicy": "on-request"})
                tid = result["thread"]["id"]
                turn(rpc, tid, "请记住项目标识 POOL_SENTINEL_42。不使用工具。")
            session = Session.create(root / "runtime", tid, "a", homes, root, {})
            sync = Syncer(session)
            cp = sync.sync(config.accounts, frozen=True)
            self.assertEqual(cp["digest"], snapshot(homes["b"], tid)["digest"])
            for name in ("b", "c", "a"):
                session.state["active_account"] = name
                session.save()
                with open_server(name) as rpc:
                    rpc.call("thread/resume", {"threadId": tid, "excludeTurns": True})
                    history = rpc.call("thread/turns/list", {"threadId": tid, "itemsView": "full", "limit": 100})
                    self.assertIn("POOL_SENTINEL_42", json.dumps(history))
                    turn(rpc, tid, "继续并记录进度。")
                sync.sync(config.accounts, frozen=True)
            for name in homes:
                self.assertEqual(snapshot(homes[name], tid)["digest"], session.load_checkpoint()["digest"])
            self.assertEqual(len(provider.requests), 4)
            last = json.dumps(provider.requests[-1], ensure_ascii=False)
            for marker in ["POOL_SENTINEL_42", "CHECKPOINT_1", "CHECKPOINT_2", "CHECKPOINT_3"]:
                self.assertIn(marker, last)

    def test_authenticated_backend_transport(self):
        with tempfile.TemporaryDirectory(prefix="pool-backend-") as tmp, Provider() as provider:
            root = Path(tmp)
            home = root / "a"
            home.mkdir()
            config = Config(("a",), {"a": home}, 10, 15, False, shutil.which("codex"))
            backend = Backend(config, "a", root, root / "backend", provider.args())
            try:
                self.assertIn("account", backend.rpc.call("account/read", {"refreshToken": False}))
            finally:
                backend.close()
