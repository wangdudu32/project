"""Session checkpoints and safe per-thread replication across account homes."""
from __future__ import annotations
from pathlib import Path
import base64
import contextlib
import fcntl
import gzip
import hashlib
import json
import os
import sqlite3
import tempfile
import time
import uuid
import tomllib

class PoolError(Exception):
    pass


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def encoded(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode()


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default
    except (ValueError, OSError) as exc:
        raise PoolError(f"无法读取 {path}：{type(exc).__name__}") from exc


def atomic_write(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=".pool-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)


def write_json(path: Path, value):
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2,
                                 allow_nan=False).encode() + b"\n")


class Lock:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.file = path.open("a+")
        try:
            fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self.file.close()
            raise PoolError(f"已有控制器或 Codex 正在使用：{path.name}") from exc

    def close(self):
        self.file.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


SUPPORTED_VERSION = "0.163.0"


DATABASES = {
    "state_5.sqlite": {"threads": "id", "thread_dynamic_tools": "thread_id",
                       "thread_spawn_edges": "parent_thread_id", "thread_attachments": "thread_id"},
    "thread_history_1.sqlite": {"thread_turns": "thread_id", "thread_items": "thread_id",
                                "thread_history_projection_state": "thread_id", "thread_realtime_items": "thread_id"},
    "goals_1.sqlite": {"thread_goals": "thread_id", "thread_goal_continuation_deferrals": "thread_id"},
    "queue_1.sqlite": {"queued_items": "thread_id", "queued_thread_revisions": "thread_id"},
}


def checked_id(value):
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise PoolError("会话 ID 必须是 UUID") from exc


def connect(path: Path, readonly=True):
    # Codex can leave a WAL needing recovery when a query process exits. Open
    # the existing DB read/write so SQLite can recover it, then forbid SQL writes
    # on snapshot connections. mode=rw still refuses to create a missing DB.
    db = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, timeout=10)
    if readonly:
        db.execute("PRAGMA query_only=ON")
    db.row_factory = sqlite3.Row
    return db


def pack(value):
    if isinstance(value, bytes):
        return {"$blob": base64.b64encode(value).decode()}
    if isinstance(value, dict):
        return {k: pack(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [pack(v) for v in value]
    return value


def unpack(value):
    if isinstance(value, dict):
        if set(value) == {"$blob"}:
            return base64.b64decode(value["$blob"])
        return {k: unpack(v) for k, v in value.items()}
    if isinstance(value, list):
        return [unpack(v) for v in value]
    return value


def rows(db, table, key, ids):
    placeholders = ",".join("?" for _ in ids)
    return [dict(row) for row in db.execute(f'SELECT * FROM "{table}" WHERE "{key}" IN ({placeholders})', ids)]


def thread_ids(home: Path, root_id: str):
    path = home / "state_5.sqlite"
    if not path.exists():
        return []
    with contextlib.closing(connect(path)) as db:
        if not db.execute("SELECT 1 FROM threads WHERE id=?", (root_id,)).fetchone():
            return []
        ids = [root_id]
        for parent in ids:
            for row in db.execute("SELECT child_thread_id FROM thread_spawn_edges WHERE parent_thread_id=?", (parent,)):
                child = checked_id(row[0])
                if child not in ids:
                    ids.append(child)
                if len(ids) > 256:
                    raise PoolError("会话树过大，停止自动迁移")
        return ids


def normalize_tables(dbname, tables):
    result = {}
    for table, records in tables.items():
        normalized = []
        for original in records:
            row = dict(original)
            if table == "threads":
                row["rollout_path"] = Path(row["rollout_path"]).name
                # Foreign keys into account-local organization are not portable.
                for key in ("project_id", "thread_section_id", "section_position", "section_entered_at_ms"):
                    if key in row:
                        row[key] = None
            elif table == "queued_thread_revisions":
                row.pop("revision", None)
            normalized.append(pack(row))
        result[table] = sorted(normalized, key=encoded)
    return result


def parts_of(snapshot):
    parts = {"db:" + name: digest(encoded(normalize_tables(name, tables)))
             for name, tables in snapshot["tables"].items() if any(tables.values())}
    for tid, rollout in snapshot["rollouts"].items():
        parts["log:" + tid] = digest(base64.b64decode(rollout["data"]))
    return parts


def comparison_parts(current, *references):
    """Ignore index-only clock changes, but keep checkpoint hashes unchanged.

    Starting an app-server rebuilds creation/update times from rollout metadata
    and mtimes, even for account queries. Accept that only when every other
    state DB field matches a verified checkpoint. Logs remain byte-checked.
    """
    if current is None:
        return {}
    parts = dict(current["parts"])
    partial = parts
    name, key = "state_5.sqlite", "db:state_5.sqlite"
    for reference in references:
        if reference is None:
            continue
        expected = {r["id"]: r for r in reference["tables"][name]["threads"]}
        tables = dict(current["tables"][name])
        tables["threads"] = [dict(row) for row in tables["threads"]]
        for row in tables["threads"]:
            for column in ("created_at", "created_at_ms", "updated_at", "updated_at_ms"):
                if column in row and column in expected.get(row["id"], {}):
                    row[column] = expected[row["id"]][column]
        candidate = digest(encoded(normalize_tables(name, tables)))
        if candidate == reference["parts"].get(key):
            partial = {**parts, key: candidate}
            if partial == reference["parts"]:
                return partial
    # A crashed installation can mix whole before/after DBs and logs; the
    # caller checks each component against the synchronization journal.
    return partial


def snapshot(home: Path, root_id: str, allow_partial=False):
    root_id = checked_id(root_id)
    ids = thread_ids(home, root_id)
    if not ids:
        return None
    result = {"format": 1, "codex_version": SUPPORTED_VERSION, "root_id": root_id,
              "ids": ids, "tables": {}, "schemas": {}, "rollouts": {}}
    with contextlib.ExitStack() as stack:
        databases = {}
        for name, tables in DATABASES.items():
            path = home / name
            if not path.exists():
                continue
            db = stack.enter_context(contextlib.closing(connect(path)))
            databases[name] = db
            db.execute("BEGIN")
            schemas = [dict(row) for row in db.execute(
                "SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY type DESC,name")]
            names = {s["name"] for s in schemas if s["type"] == "table"}
            result["tables"][name] = {t: rows(db, t, key, ids) for t, key in tables.items() if t in names}
            migrations = [dict(row) for row in db.execute("SELECT * FROM _sqlx_migrations ORDER BY version")]
            result["schemas"][name] = {"definitions": schemas, "migrations": pack(migrations)}
        threads = result["tables"]["state_5.sqlite"]["threads"]
        for thread in threads:
            if thread.get("cli_version") != SUPPORTED_VERSION:
                raise PoolError(f"会话版本 {thread.get('cli_version')} 未通过迁移验证（支持 {SUPPORTED_VERSION}）")
            path = Path(thread["rollout_path"])
            try:
                relative = path.resolve().relative_to(home.resolve())
            except ValueError as exc:
                raise PoolError("会话文件位于账号目录之外，拒绝自动迁移") from exc
            if relative.parts[0] not in ("sessions", "archived_sessions"):
                raise PoolError("不支持的会话文件位置")
            data = path.read_bytes()
            end = data.rfind(b"\n") + 1
            data = data[:end]
            if not data:
                raise PoolError("会话尚未完整落盘")
            # Preserve every raw item, including compaction and encrypted reasoning.
            try:
                first = json.loads(data.split(b"\n", 1)[0])
            except ValueError as exc:
                raise PoolError("会话元数据损坏") from exc
            if first.get("type") != "session_meta" or first.get("payload", {}).get("id") != thread["id"]:
                raise PoolError("会话文件与数据库 ID 不匹配")
            result["rollouts"][thread["id"]] = {"relative": str(relative), "data": base64.b64encode(data).decode()}
        for row in result["tables"].get("thread_history_1.sqlite", {}).get("thread_history_projection_state", []):
            data = result["rollouts"].get(row["thread_id"])
            if not allow_partial and (data is None or row["next_rollout_byte_offset"] > len(base64.b64decode(data["data"]))):
                raise PoolError("历史数据库尚未与会话文件对齐，请稍后重试")
    result["parts"] = parts_of(result)
    result["digest"] = digest(encoded(result["parts"]))
    return pack(result)


def schema_signature(rows):
    # Migration checksums detect schema drift without depending on SQL formatting.
    return [(r["version"], r["checksum"], r["success"]) for r in rows]


def initialize_db(path, schema):
    """Only initialize a missing DB, using the exact installed-version schema."""
    if path.exists():
        return
    fd, temporary = tempfile.mkstemp(prefix=".pool-schema-", dir=path.parent)
    os.close(fd)
    db = sqlite3.connect(temporary)
    try:
        with db:
            # sqlite3's context manager does not begin a transaction for DDL.
            # Commit the whole schema once, rather than fsync for every index.
            db.execute("BEGIN IMMEDIATE")
            for kind in ("table", "index", "trigger", "view"):
                for definition in schema["definitions"]:
                    if definition["type"] == kind:
                        db.execute(definition["sql"])
            for row in unpack(schema["migrations"]):
                cols = list(row)
                db.execute(f'INSERT INTO _sqlx_migrations ({",".join(cols)}) VALUES ({",".join("?" for _ in cols)})',
                           [row[c] for c in cols])
        db.close()
        try:
            # Publish only a complete database, without replacing a database
            # that a native Codex process created in the meantime.
            os.link(temporary, path)
        except FileExistsError:
            return
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        db.close()
        os.unlink(temporary)


def install(home: Path, checkpoint):
    """Caller holds all target thread writer locks and has journaled the change."""
    checkpoint = unpack(checkpoint)
    ids = checkpoint["ids"]
    # Check every database before replacing even one file. An unsupported target
    # must retain its previous usable checkpoint.
    for name in checkpoint["tables"]:
        path = home / name
        schema = checkpoint["schemas"][name]
        initialize_db(path, schema)
        with contextlib.closing(connect(path)) as db:
            migration_rows = [dict(r) for r in db.execute("SELECT * FROM _sqlx_migrations ORDER BY version")]
            if schema_signature(migration_rows) != schema_signature(schema["migrations"]):
                raise PoolError(f"{home.name}/{name} 数据库版本不匹配")
    for tid, rollout in checkpoint["rollouts"].items():
        relative = Path(rollout["relative"])
        if relative.is_absolute() or ".." in relative.parts or relative.parts[0] not in ("sessions", "archived_sessions"):
            raise PoolError("检查点包含非法路径")
        atomic_write(home / relative, base64.b64decode(rollout["data"]))
    for name, tables in checkpoint["tables"].items():
        path = home / name
        schema = checkpoint["schemas"][name]
        initialize_db(path, schema)
        with contextlib.closing(connect(path, readonly=False)) as db:
            migration_rows = [dict(r) for r in db.execute("SELECT * FROM _sqlx_migrations ORDER BY version")]
            if schema_signature(migration_rows) != schema_signature(schema["migrations"]):
                raise PoolError(f"{home.name}/{name} 数据库版本不匹配")
            with db:
                # Child rows before parent rows, then parents before children.
                for table in reversed(list(tables)):
                    key = DATABASES[name][table]
                    db.execute(f'DELETE FROM "{table}" WHERE "{key}" IN ({",".join("?" for _ in ids)})', ids)
                for table, records in tables.items():
                    for record in records:
                        row = dict(record)
                        if table == "threads":
                            row["rollout_path"] = str(home / checkpoint["rollouts"][row["id"]]["relative"])
                            for key in ("project_id", "thread_section_id", "section_position", "section_entered_at_ms"):
                                if key in row:
                                    row[key] = None
                        elif table == "queued_thread_revisions":
                            row.pop("revision", None)
                        columns = list(row)
                        names = ",".join('"' + c + '"' for c in columns)
                        db.execute(f'INSERT INTO "{table}" ({names}) VALUES ({",".join("?" for _ in columns)})',
                                   [row[c] for c in columns])


class Session:
    def __init__(self, directory: Path):
        self.directory = directory
        self.path = directory / "state.json"
        self.state = read_json(self.path)
        if not isinstance(self.state, dict) or self.state.get("format") != 1:
            raise PoolError(f"无效的额度池会话：{directory.name}")

    @classmethod
    def create(cls, runtime: Path, tid, account, homes, cwd, settings):
        tid = checked_id(tid)
        directory = runtime / tid
        directory.mkdir(parents=True, exist_ok=False, mode=0o700)
        write_json(directory / "state.json", {"format": 1, "id": tid, "active_account": account,
                   "homes": {k: str(v) for k, v in homes.items()}, "cwd": str(cwd), "settings": settings,
                   "status": "starting", "revision": 0, "replicas": {}, "updated_at": time.time(),
                   "pending_sync": None, "checkpoint": None, "controller": None, "backend": None})
        return cls(directory)

    def save(self):
        self.state["updated_at"] = time.time()
        write_json(self.path, self.state)

    def log(self, event, **details):
        with (self.directory / "events.jsonl").open("ab") as stream:
            stream.write(encoded({"at": time.time(), "event": event, **details}) + b"\n")

    def load_checkpoint(self, name=None):
        name = name or self.state.get("checkpoint")
        if not name:
            return None
        path = self.directory / name
        data = json.loads(gzip.decompress(path.read_bytes()))
        if data.get("format") != 1 or parts_of(data) != data.get("parts") or digest(encoded(data["parts"])) != data.get("digest"):
            raise PoolError("检查点校验失败，拒绝恢复")
        return data


class Syncer:
    def __init__(self, session: Session):
        self.session = session

    def sync(self, accounts, frozen=False, use_checkpoint=False):
        session, state = self.session, self.session.state
        homes = {k: Path(v) for k, v in state["homes"].items()}
        active = state["active_account"]
        previous = session.load_checkpoint()
        # Finish an interrupted installation before accepting a newer revision.
        if state.get("pending_sync") or use_checkpoint:
            cp = previous
        else:
            cp = snapshot(homes[active], state["id"])
            if cp is None:
                raise PoolError("权威账号中的会话不存在")
        if cp is None:
            raise PoolError("尚无可恢复的检查点")
        changed = previous is None or cp["digest"] != previous["digest"]
        if changed:
            state["revision"] += 1
            name = f"checkpoints/{state['revision']:08d}.json.gz"
            atomic_write(session.directory / name, gzip.compress(encoded(cp), mtime=0))
            state["checkpoint"] = name
        revision = state["revision"]
        journal = state.get("pending_sync") or {"revision": revision, "targets": {}}
        state["pending_sync"] = journal
        session.save()
        for account in accounts:
            if account == active and not use_checkpoint:
                state["replicas"][account] = {"revision": revision, "digest": cp["digest"]}
                continue
            home = homes[account]
            with contextlib.ExitStack() as stack:
                for tid in sorted(cp["ids"]):
                    stack.enter_context(Lock(home / "thread-writer-locks" / (tid + ".lock")))
                entry = journal["targets"].get(account)
                current = snapshot(home, state["id"], allow_partial=bool(entry))
                replica = state["replicas"].get(account, {})
                before = None
                if replica:
                    old_name = f"checkpoints/{replica['revision']:08d}.json.gz"
                    if (session.directory / old_name).exists():
                        before = session.load_checkpoint(old_name)
                        if before["digest"] != replica["digest"]:
                            raise PoolError("副本检查点校验失败，拒绝覆盖")
                current_parts = comparison_parts(current, cp, before)
                current_digest = digest(encoded(current_parts)) if current else None
                if current_digest == cp["digest"] and (not frozen or current["digest"] == cp["digest"]):
                    state["replicas"][account] = {"revision": revision, "digest": cp["digest"]}
                    session.save()
                    continue
                if entry:
                    # Each independently committed component must still be one
                    # of the journal's before/after values. Refuse foreign edits.
                    keys = set(current_parts) | set(entry["before"]) | set(cp["parts"])
                    if any(current_parts.get(k) not in (entry["before"].get(k), cp["parts"].get(k)) for k in keys):
                        raise PoolError(f"{account} 会话发生分叉，已保留两边数据并停止同步")
                else:
                    expected = replica.get("digest")
                    if current_digest not in (expected, cp["digest"]):
                        raise PoolError(f"{account} 会话已在额度池外修改，拒绝覆盖")
                    journal["targets"][account] = {"before": current_parts}
                    session.save()
                install(home, cp)
                verify = snapshot(home, state["id"])
                if verify is None or comparison_parts(verify, cp) != cp["parts"]:
                    raise PoolError(f"{account} 同步后校验失败")
                state["replicas"][account] = {"revision": revision, "digest": cp["digest"]}
                session.save()
        state["pending_sync"] = None
        state["last_sync_at"] = time.time()
        state["last_sync_frozen"] = frozen
        session.save()
        if changed:
            session.log("synchronized", revision=revision, accounts=list(accounts), frozen=frozen)
        # Only remove old pool-owned checkpoints after a fully verified sync.
        saved = sorted((session.directory / "checkpoints").glob("[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9].json.gz"))
        for old in saved[:-3]:
            if old != session.directory / state["checkpoint"]:
                old.unlink()
        return cp


FIELDS = {"input_tokens": "inputTokens", "cached_input_tokens": "cachedInputTokens",
          "output_tokens": "outputTokens", "reasoning_output_tokens": "reasoningOutputTokens"}


def normalize_usage(raw):
    if not isinstance(raw, dict):
        return None
    usage = {key: raw.get(key, raw.get(camel)) for key, camel in FIELDS.items()}
    if any(type(value) is not int or value < 0 for value in usage.values()):
        return None
    if usage["cached_input_tokens"] > usage["input_tokens"]:
        return None
    return usage


def checkpoint_usage(checkpoint, tid):
    if not checkpoint:
        return None
    rollout = checkpoint.get("rollouts", {}).get(tid)
    if not rollout:
        return None
    for line in reversed(base64.b64decode(rollout["data"]).splitlines()):
        if b'"token_count"' not in line:
            continue
        try:
            event = json.loads(line)
        except (ValueError, UnicodeError):
            continue
        payload = event.get("payload", {})
        if event.get("type") == "event_msg" and payload.get("type") == "token_count":
            usage = normalize_usage((payload.get("info") or {}).get("total_token_usage"))
            if usage is not None:
                return usage
    return None


def check_home_layout(home: Path):
    if not home.is_dir():
        raise PoolError(f"账号目录不存在：{home}")
    path = home / "config.toml"
    try:
        settings = tomllib.loads(path.read_text()) if path.exists() else {}
    except (ValueError, OSError) as exc:
        raise PoolError(f"无法读取账号配置：{path}") from exc
    sqlite_home = settings.get("sqlite_home")
    if sqlite_home is not None and (not isinstance(sqlite_home, str) or
                                   Path(sqlite_home).expanduser().resolve() != home.resolve()):
        raise PoolError(f"{home.name} 使用独立 sqlite_home，本版本尚未支持这种存储布局")
