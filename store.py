import hashlib
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

import numpy as np

from config import DB_PATH, EMBED_DIM

_write_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    session_id TEXT,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    ts_ms INTEGER,
    embedding BLOB,
    kind TEXT NOT NULL DEFAULT 'chunk',
    superseded_by TEXT,
    topic TEXT
);
CREATE INDEX IF NOT EXISTS idx_mem_user ON memories(user_id);
CREATE INDEX IF NOT EXISTS idx_mem_session ON memories(session_id);
CREATE INDEX IF NOT EXISTS idx_mem_user_topic ON memories(user_id, kind, topic);
CREATE VIRTUAL TABLE IF NOT EXISTS mem_fts USING fts5(fid UNINDEXED, user_id UNINDEXED, content);
CREATE TABLE IF NOT EXISTS embed_cache (
    hash TEXT PRIMARY KEY,
    embedding BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS processed_requests (
    request_id TEXT PRIMARY KEY
);
"""


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    return con


con = _connect()
con.executescript(SCHEMA)


def _ensure_columns() -> None:
    cols = {r[1] for r in con.execute("PRAGMA table_info(memories)").fetchall()}
    if "kind" not in cols:
        con.execute("ALTER TABLE memories ADD COLUMN kind TEXT NOT NULL DEFAULT 'chunk'")
    if "superseded_by" not in cols:
        con.execute("ALTER TABLE memories ADD COLUMN superseded_by TEXT")
    if "topic" not in cols:
        con.execute("ALTER TABLE memories ADD COLUMN topic TEXT")
    con.commit()


_ensure_columns()
con.commit()


def get_rollup(user_id: str, topic: str) -> dict | None:
    row = con.execute(
        "SELECT id, content FROM memories WHERE user_id = ? AND kind = 'rollup' AND topic = ? LIMIT 1",
        (user_id, topic),
    ).fetchone()
    return {"id": row[0], "content": row[1]} if row else None


def upsert_rollup(user_id: str, session_id: str, topic: str, content: str, ts_ms: int | None) -> str:
    existing = get_rollup(user_id, topic)
    created_at = iso_from_ms(ts_ms)
    if existing:
        fid = existing["id"]
        with _write_lock:
            vec_table.invalidate(user_id)
        return fid
    mid = new_id()
    with _write_lock:
        con.execute(
            "INSERT INTO memories(id, user_id, session_id, content, created_at, ts_ms, embedding, kind, topic) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'rollup', ?)",
            (mid, user_id, session_id, content, created_at, ts_ms, None, topic),
        )
        con.execute(
            "INSERT INTO mem_fts(fid, user_id, content) VALUES (?, ?, ?)",
            (mid, user_id, content),
        )
        con.commit()
    vec_table.invalidate(user_id)
    return mid


def update_memory_content(fid: str, content: str, embedding: list[float] | None, ts_ms: int | None, created_at: str) -> None:
    blob = np.asarray(embedding, dtype=np.float32).tobytes() if embedding is not None else None
    with _write_lock:
        row = con.execute("SELECT user_id FROM memories WHERE id = ?", (fid,)).fetchone()
        if not row:
            return
        con.execute(
            "UPDATE memories SET content = ?, embedding = COALESCE(?, embedding), ts_ms = COALESCE(?, ts_ms), created_at = ? WHERE id = ?",
            (content, blob, ts_ms, created_at, fid),
        )
        con.execute("DELETE FROM mem_fts WHERE fid = ?", (fid,))
        con.execute(
            "INSERT INTO mem_fts(fid, user_id, content) VALUES (?, ?, ?)",
            (fid, row[0], content),
        )
        con.commit()
    vec_table.invalidate(row[0])


def set_embedding(fid: str, embedding: list[float]) -> None:
    blob = np.asarray(embedding, dtype=np.float32).tobytes()
    with _write_lock:
        row = con.execute("SELECT user_id FROM memories WHERE id = ?", (fid,)).fetchone()
        if not row:
            return
        con.execute("UPDATE memories SET embedding = ? WHERE id = ?", (blob, fid))
        con.commit()
    vec_table.invalidate(row[0])


def supersede(old_id: str, new_id: str) -> None:
    with _write_lock:
        con.execute(
            "UPDATE memories SET superseded_by = ? WHERE id = ?",
            (new_id, old_id),
        )
        con.commit()


def new_id() -> str:
    return uuid.uuid4().hex


def request_seen(request_id: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM processed_requests WHERE request_id = ?", (request_id,)
    ).fetchone()
    return row is not None


def mark_request(request_id: str) -> None:
    with _write_lock:
        con.execute(
            "INSERT OR IGNORE INTO processed_requests(request_id) VALUES (?)",
            (request_id,),
        )
        con.commit()


def iso_from_ms(ts_ms: int | None) -> str:
    if ts_ms is None:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )


def date_from_ms(ts_ms: int | None) -> str | None:
    if ts_ms is None:
        return None
    return datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")


def embed_cache_get(texts: list[str]) -> tuple[list[list[float] | None], list[int], list[str]]:
    hashes = [hashlib.sha1(t.encode("utf-8")).hexdigest() for t in texts]
    results: list[list[float] | None] = [None] * len(texts)
    missing_idx: list[int] = []
    missing_hash: list[str] = []
    for i, h in enumerate(hashes):
        row = con.execute(
            "SELECT embedding FROM embed_cache WHERE hash = ?", (h,)
        ).fetchone()
        if row is not None:
            results[i] = list(np.frombuffer(row[0], dtype=np.float32))
        else:
            missing_idx.append(i)
            missing_hash.append(h)
    return results, missing_idx, missing_hash


def embed_cache_put(texts: list[str], vectors: list[list[float]]) -> None:
    with _write_lock:
        for t, v in zip(texts, vectors):
            h = hashlib.sha1(t.encode("utf-8")).hexdigest()
            arr = np.asarray(v, dtype=np.float32)
            con.execute(
                "INSERT OR REPLACE INTO embed_cache(hash, embedding) VALUES (?, ?)",
                (h, arr.tobytes()),
            )
        con.commit()


class UserVectorTable:
    def __init__(self) -> None:
        self._cache: dict[str, tuple[int, np.ndarray, list[str]]] = {}

    def _load(self, user_id: str) -> tuple[np.ndarray, list[str]]:
        rows = con.execute(
            "SELECT id, embedding FROM memories WHERE user_id = ? AND embedding IS NOT NULL",
            (user_id,),
        ).fetchall()
        ids = [r[0] for r in rows]
        if not rows:
            mat = np.zeros((0, EMBED_DIM), dtype=np.float32)
        else:
            mat = np.frombuffer(b"".join(r[1] for r in rows), dtype=np.float32).reshape(
                len(rows), EMBED_DIM
            )
        self._cache[user_id] = (len(ids), mat, ids)
        return mat, ids

    def get(self, user_id: str) -> tuple[np.ndarray, list[str]]:
        rows = con.execute(
            "SELECT COUNT(*) FROM memories WHERE user_id = ? AND embedding IS NOT NULL",
            (user_id,),
        ).fetchone()[0]
        cached = self._cache.get(user_id)
        if cached is not None and cached[0] == rows:
            return cached[1], cached[2]
        return self._load(user_id)

    def invalidate(self, user_id: str) -> None:
        self._cache.pop(user_id, None)


vec_table = UserVectorTable()


def insert_memories(
    items: list[dict],
    embeddings: list[list[float]] | None,
    kind: str = "chunk",
) -> list[str]:
    ids: list[str] = []
    with _write_lock:
        for n, item in enumerate(items):
            mid = new_id()
            ids.append(mid)
            blob = (
                np.asarray(embeddings[n], dtype=np.float32).tobytes()
                if embeddings is not None
                else None
            )
            con.execute(
                "INSERT INTO memories(id, user_id, session_id, content, created_at, ts_ms, embedding, kind) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    mid,
                    item["user_id"],
                    item.get("session_id"),
                    item["content"],
                    item["created_at"],
                    item.get("ts_ms"),
                    blob,
                    item.get("kind", kind),
                ),
            )
            con.execute(
                "INSERT INTO mem_fts(fid, user_id, content) VALUES (?, ?, ?)",
                (mid, item["user_id"], item["content"]),
            )
        con.commit()
    if items:
        vec_table.invalidate(items[0]["user_id"])
    return ids


def keyword_search(user_id: str, query: str, limit: int) -> list[tuple[str, float]]:
    sanitized = "".join(ch if ch.isalnum() else " " for ch in query)
    tokens = [t for t in sanitized.split() if t]
    if not tokens:
        return []
    match_expr = " OR ".join(f'"{t}"' for t in tokens[:24])
    try:
        rows = con.execute(
            "SELECT fid, bm25(mem_fts) FROM mem_fts "
            "WHERE mem_fts MATCH ? AND user_id = ? ORDER BY rank LIMIT ?",
            (match_expr, user_id, limit),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [(r[0], -float(r[1])) for r in rows]


def fetch_contents(ids: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for i in range(0, len(ids), 100):
        chunk = ids[i : i + 100]
        qmarks = ",".join("?" * len(chunk))
        rows = con.execute(
            f"SELECT id, content, created_at, superseded_by, kind FROM memories WHERE id IN ({qmarks})",
            chunk,
        ).fetchall()
        for r in rows:
            out[r[0]] = {
                "id": r[0],
                "content": r[1],
                "created_at": r[2],
                "superseded_by": r[3],
                "kind": r[4],
            }
    return out


def superseded_ids(ids: list[str]) -> set[str]:
    found = fetch_contents(ids)
    return {fid for fid, info in found.items() if info.get("superseded_by")}
