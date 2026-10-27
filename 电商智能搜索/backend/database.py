"""Explicit SQLite queries; each operation owns and closes its connection."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

import settings


@contextmanager
def connect():
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(settings.database_path, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database():
    with connect() as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                brand TEXT NOT NULL,
                category TEXT NOT NULL,
                color TEXT NOT NULL,
                price REAL NOT NULL CHECK(price >= 0),
                original_price REAL NOT NULL,
                stock INTEGER NOT NULL CHECK(stock >= 0),
                popularity INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                search_text TEXT NOT NULL,
                data TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS product_filters ON products(category, brand, price);
            CREATE VIRTUAL TABLE IF NOT EXISTS product_search
                USING fts5(product_id UNINDEXED, words, tokenize='unicode61');
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                state TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS message_session ON messages(session_id, id);
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                product_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)


def save_products(products, tokenized_texts):
    """Replace one snapshot atomically; duplicate IDs cannot create duplicate rows."""
    with connect() as connection:
        connection.execute("DELETE FROM product_search")
        connection.execute("DELETE FROM products")
        connection.executemany(
            "INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    item["id"],
                    item["name"],
                    item["brand"],
                    item["category"],
                    item["color"],
                    item["price"],
                    item["original_price"],
                    item["stock"],
                    item["popularity"],
                    item["created_at"],
                    item["search_text"],
                    json.dumps(item, ensure_ascii=False),
                )
                for item in products
            ],
        )
        connection.executemany(
            "INSERT INTO product_search(product_id, words) VALUES (?, ?)",
            [(item["id"], words) for item, words in zip(products, tokenized_texts)],
        )


def product_count():
    with connect() as connection:
        return connection.execute("SELECT count(*) FROM products").fetchone()[0]


def get_product(product_id):
    with connect() as connection:
        row = connection.execute(
            "SELECT data FROM products WHERE id = ?", (product_id,)
        ).fetchone()
    return json.loads(row["data"]) if row else None


def select_products(filters, product_ids=None):
    clauses = ["1 = 1"]
    parameters = []
    for field in ("category", "brand", "color"):
        if filters.get(field):
            clauses.append(f"{field} = ?")
            parameters.append(filters[field])
    if filters.get("min_price") is not None:
        clauses.append("price >= ?")
        parameters.append(filters["min_price"])
    if filters.get("max_price") is not None:
        clauses.append("price <= ?")
        parameters.append(filters["max_price"])
    if filters.get("in_stock", True):
        clauses.append("stock > 0")
    for tag in filters.get("exclude_tags", []):
        # instr treats user text literally, including %, _ and quotes.
        clauses.append("instr(lower(search_text), lower(?)) = 0")
        parameters.append(tag)
    if product_ids is not None:
        if not product_ids:
            return []
        clauses.append("id IN (" + ",".join("?" for item in product_ids) + ")")
        parameters.extend(product_ids)
    query = "SELECT data FROM products WHERE " + " AND ".join(clauses)
    with connect() as connection:
        rows = connection.execute(query, parameters).fetchall()
    return [json.loads(row["data"]) for row in rows]


def keyword_candidates(words, allowed_ids, limit=120):
    if not words or not allowed_ids:
        return []
    expression = " OR ".join('"' + word.replace('"', '""') + '"' for word in words)
    with connect() as connection:
        rows = connection.execute(
            "SELECT product_id, bm25(product_search) AS score FROM product_search "
            "WHERE product_search MATCH ? ORDER BY score LIMIT 2000",
            (expression,),
        ).fetchall()
    return [row["product_id"] for row in rows if row["product_id"] in allowed_ids][
        :limit
    ]


def get_facets():
    with connect() as connection:
        categories = [
            dict(row)
            for row in connection.execute(
                "SELECT category AS name, count(*) AS count FROM products GROUP BY category"
            )
        ]
        brands = [
            row[0]
            for row in connection.execute(
                "SELECT DISTINCT brand FROM products ORDER BY brand"
            )
        ]
        colors = [
            row[0]
            for row in connection.execute(
                "SELECT DISTINCT color FROM products ORDER BY color"
            )
        ]
        total = connection.execute("SELECT count(*) FROM products").fetchone()[0]
    return {
        "categories": categories,
        "brands": brands,
        "colors": colors,
        "total": total,
    }


def load_session(session_id=None):
    if session_id:
        with connect() as connection:
            row = connection.execute(
                "SELECT state FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
        if row:
            return session_id, json.loads(row["state"])
        raise LookupError("会话不存在，请开始新对话")
    session_id = str(uuid4())
    state = {"query": "", "filters": {}, "product_ids": []}
    with connect() as connection:
        connection.execute(
            "INSERT INTO sessions VALUES (?, ?, ?)",
            (
                session_id,
                json.dumps(state),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
    return session_id, state


def save_turn(session_id, state, user_message, answer):
    now = datetime.now(timezone.utc).isoformat()
    with connect() as connection:
        connection.execute(
            "UPDATE sessions SET state = ? WHERE id = ?",
            (
                json.dumps(state, ensure_ascii=False),
                session_id,
            ),
        )
        connection.executemany(
            "INSERT INTO messages(session_id, role, content, payload, created_at) VALUES (?, ?, ?, ?, ?)",
            [
                (session_id, "user", user_message, "{}", now),
                (
                    session_id,
                    "assistant",
                    answer["message"],
                    json.dumps(answer, ensure_ascii=False),
                    now,
                ),
            ],
        )


def get_messages(session_id, limit=20):
    with connect() as connection:
        rows = connection.execute(
            "SELECT role, content, payload FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
    return [
        {
            "role": row["role"],
            "content": row["content"],
            "payload": json.loads(row["payload"]),
        }
        for row in reversed(rows)
    ]


def delete_session(session_id):
    with connect() as connection:
        connection.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        connection.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


def record_event(kind, product_id):
    with connect() as connection:
        connection.execute(
            "INSERT INTO events(kind, product_id, created_at) VALUES (?, ?, ?)",
            (
                kind,
                product_id,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
