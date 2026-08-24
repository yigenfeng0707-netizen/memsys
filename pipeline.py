import asyncio
import json
import re
import time

import numpy as np

from config import (
    CHUNK_MAX_CHARS,
    CHUNKS_ENABLED,
    CONFLICT_HIGH,
    CONFLICT_LOW,
    DEDUP_THRESHOLD,
    EXTRACT_FACTS,
    KEYWORD_CANDIDATES,
    MAX_CONFLICT_JUDGES_PER_ADD,
    MAX_FACTS_PER_ADD,
    RESULT_CAP,
    RRF_K,
    TRIM_CHUNK_LINES,
    VECTOR_CANDIDATES,
)
from extract import extract_facts, judge_conflict, merge_profile, merge_rollup, rerank_passages
from llm import llm
from store import (
    date_from_ms,
    embed_cache_get,
    embed_cache_put,
    fetch_contents,
    get_rollup,
    insert_memories,
    iso_from_ms,
    keyword_search,
    request_seen,
    mark_request,
    set_embedding,
    supersede,
    update_memory_content,
    upsert_rollup,
    vec_table,
)


def chunk_messages(messages: list[dict], user_id: str, session_id: str) -> list[dict]:
    items: list[dict] = []
    buf: list[str] = []
    buf_chars = 0
    last_ts: int | None = None

    def flush() -> None:
        nonlocal buf, buf_chars
        if not buf:
            return
        items.append(
            {
                "user_id": user_id,
                "session_id": session_id,
                "content": "\n".join(buf).strip(),
                "created_at": iso_from_ms(last_ts),
                "ts_ms": last_ts,
            }
        )
        buf = []
        buf_chars = 0

    for msg in messages:
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        ts = msg.get("timestamp")
        role = msg.get("role", "user")
        date_str = date_from_ms(ts)
        line = f"[{date_str}] {role}: {content}" if date_str else f"{role}: {content}"
        if buf and buf_chars + len(line) > CHUNK_MAX_CHARS:
            flush()
        buf.append(line)
        buf_chars += len(line)
        if ts is not None:
            last_ts = ts
    flush()
    return items


def _debug(msg: str) -> None:
    from config import BASE_DIR, DEBUG_LOG
    if not DEBUG_LOG:
        return
    try:
        with open(BASE_DIR / "server_debug.log", "a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    except Exception:
        pass


async def _embed_with_cache(texts: list[str]) -> list[list[float]]:
    cached, missing_idx, _ = embed_cache_get(texts)
    if missing_idx:
        fresh = await llm.embed([texts[i] for i in missing_idx])
        for pos, idx in enumerate(missing_idx):
            cached[idx] = fresh[pos]
        embed_cache_put([texts[i] for i in missing_idx], fresh)
    return cached


def _top_matches(matrix: np.ndarray, ids: list[str], vec: np.ndarray, n: int) -> list[tuple[str, float]]:
    if matrix.shape[0] == 0:
        return []
    norms = np.linalg.norm(matrix, axis=1) * (np.linalg.norm(vec) + 1e-9)
    sims = (matrix @ vec) / np.where(norms == 0, 1e-9, norms)
    order = np.argsort(-sims)[:n]
    return [(ids[i], float(sims[i])) for i in order]


async def _process_facts(
    items: list[dict],
    user_id: str,
) -> None:
    profile = get_rollup(user_id, "__profile__")
    context = profile["content"] if profile else None
    fact_lists = await asyncio.gather(*[extract_facts(it["content"], context) for it in items])
    fact_specs: list[dict] = []
    for it, facts in zip(items, fact_lists):
        for f in facts:
            ts = f["timestamp"] if f["timestamp"] is not None else it.get("ts_ms")
            date_str = date_from_ms(ts)
            prefix = f"[{date_str}] " if date_str else ""
            fact_specs.append(
                {
                    "user_id": user_id,
                    "session_id": it["session_id"],
                    "content": (prefix + f["content"]).strip(),
                    "created_at": iso_from_ms(ts),
                    "ts_ms": ts,
                    "kind": f["kind"],
                }
            )
            if len(fact_specs) >= MAX_FACTS_PER_ADD:
                break
        if len(fact_specs) >= MAX_FACTS_PER_ADD:
            break
    if not fact_specs:
        return

    texts = [fs["content"] for fs in fact_specs]
    vectors = await _embed_with_cache(texts)

    matrix, ids = vec_table.get(user_id)
    survivors: list[int] = []
    supersede_pairs: list[tuple[str, int]] = []

    match_lists = [
        _top_matches(matrix, ids, np.asarray(v, dtype=np.float32), 3)
        for v in vectors
    ]

    judge_plan: list[tuple[int, str]] = []
    skip_dup: set[int] = set()
    for fi, matches in enumerate(match_lists):
        if not matches:
            survivors.append(fi)
            continue
        best_sim = matches[0][1]
        if best_sim >= DEDUP_THRESHOLD:
            skip_dup.add(fi)
            continue
        candidates = [m for m in matches if CONFLICT_LOW <= m[1] < CONFLICT_HIGH]
        if not candidates:
            survivors.append(fi)
            continue
        for old_id, _sim in candidates[:2]:
            judge_plan.append((fi, old_id))
    judge_plan = judge_plan[:MAX_CONFLICT_JUDGES_PER_ADD]

    all_old_ids = [old_id for _, old_id in judge_plan]
    old_contents = fetch_contents(all_old_ids)

    async def run_judge(fi: int, old_id: str) -> tuple[int, str, str]:
        info = old_contents.get(old_id)
        label = await judge_conflict(info["content"], fact_specs[fi]["content"]) if info else "RELATED"
        return fi, old_id, label

    verdicts_by_fi: dict[int, list[tuple[str, str]]] = {}
    if judge_plan:
        results_j = await asyncio.gather(*[run_judge(fi, oid) for fi, oid in judge_plan])
        for fi, old_id, label in results_j:
            verdicts_by_fi.setdefault(fi, []).append((old_id, label))

    judged_fis = set(verdicts_by_fi)
    for fi in range(len(fact_specs)):
        if fi in skip_dup:
            continue
        if fi not in judged_fis and fi not in survivors:
            survivors.append(fi)

    for fi, verdicts in verdicts_by_fi.items():
        if any(label == "DUPLICATE" for _, label in verdicts):
            continue
        for old_id, label in verdicts:
            if label == "OUTDATED":
                supersede_pairs.append((old_id, fi))
        survivors.append(fi)

    if not survivors:
        return
    inserted_items = [fact_specs[fi] for fi in survivors]
    inserted_vecs = [vectors[fi] for fi in survivors]
    new_ids = insert_memories(inserted_items, inserted_vecs)
    id_of_fi = {fi: new_ids[survivors.index(fi)] for fi in survivors}
    for old_id, fi in supersede_pairs:
        nid = id_of_fi.get(fi)
        if nid:
            supersede(old_id, nid)

    await _update_rollups(user_id, inserted_items)
    await _update_profile(user_id, inserted_items)


async def _update_profile(user_id: str, fact_items: list[dict]) -> None:
    if not fact_items:
        return
    try:
        existing = get_rollup(user_id, "__profile__")
        merged = await merge_profile(existing["content"] if existing else None, [it["content"] for it in fact_items])
        if not merged:
            return
        last_ts = max((it.get("ts_ms") or 0) for it in fact_items) or None
        if existing:
            update_memory_content(existing["id"], merged, None, last_ts, iso_from_ms(last_ts))
            vec = (await _embed_with_cache([merged]))[0]
            set_embedding(existing["id"], vec)
        else:
            fid = upsert_rollup(user_id, fact_items[0].get("session_id"), "__profile__", merged, last_ts)
            vec = (await _embed_with_cache([merged]))[0]
            set_embedding(fid, vec)
    except Exception as exc:
        _debug(f"profile error: {exc}")


async def _update_rollups(user_id: str, fact_items: list[dict]) -> None:
    by_topic: dict[str, list[dict]] = {}
    for it in fact_items:
        by_topic.setdefault(it.get("topic", "general"), []).append(it)
    for topic, items in by_topic.items():
        try:
            existing = get_rollup(user_id, topic)
            merged = await merge_rollup(existing["content"] if existing else None, [it["content"] for it in items])
            if not merged:
                _debug(f"rollup merge empty topic={topic}")
                continue
            last_ts = max((it.get("ts_ms") or 0) for it in items) or None
            if existing:
                update_memory_content(existing["id"], merged, None, last_ts, iso_from_ms(last_ts))
                vec = (await _embed_with_cache([merged]))[0]
                set_embedding(existing["id"], vec)
            else:
                fid = upsert_rollup(user_id, items[0].get("session_id"), topic, merged, last_ts)
                vec = (await _embed_with_cache([merged]))[0]
                set_embedding(fid, vec)
            _debug(f"rollup updated topic={topic} len={len(merged)} existing={bool(existing)}")
        except Exception as exc:
            _debug(f"rollup error topic={topic}: {exc}")
            continue


async def run_add(request_id: str, messages: list[dict], user_id: str, session_id: str) -> None:
    if request_seen(request_id):
        return
    items = chunk_messages(messages, user_id, session_id)
    if items:
        texts = [it["content"] for it in items]
        cached = await _embed_with_cache(texts)
        insert_memories(items, cached, kind="chunk")
        vec_table.invalidate(user_id)
        if EXTRACT_FACTS:
            try:
                await _process_facts(items, user_id)
            except Exception as exc:
                _debug(f"process_facts error: {exc}")
    mark_request(request_id)


def _rrf_fuse(rank_lists: list[list[str]]) -> list[str]:
    scores: dict[str, float] = {}
    for ranks in rank_lists:
        for pos, fid in enumerate(ranks):
            scores[fid] = scores.get(fid, 0.0) + 1.0 / (RRF_K + pos + 1)
    return [k for k, _ in sorted(scores.items(), key=lambda kv: -kv[1])]


def cosine_top(matrix: np.ndarray, ids: list[str], qvec: np.ndarray, limit: int) -> list[str]:
    if matrix.shape[0] == 0:
        return []
    norms = np.linalg.norm(matrix, axis=1) * np.linalg.norm(qvec)
    sims = (matrix @ qvec) / np.where(norms == 0, 1e-9, norms)
    order = np.argsort(-sims)[:limit]
    return [ids[i] for i in order]


QUERY_EXPAND_SYSTEM = (
    "You prepare search queries for retrieving relevant lines from a long multi-session dialogue memory. "
    'Given a question, output STRICT JSON only: {"queries": ["...", "..."], "style": "attribute"|"context"} with exactly 2 queries: '
    "one natural paraphrase preserving all entity names, and one short keyword-only query of 2-6 words with the most distinctive names or nouns. "
    'Set style to "attribute" if the question asks about stable personal attributes, lists of things done/liked/owned, preferences, or current states; '
    'set it to "context" for events, stories, timelines, causality or multi-part reasoning.'
)


async def expand_query(query: str) -> tuple[list[str], str]:
    try:
        raw = await llm.chat(QUERY_EXPAND_SYSTEM, query, max_tokens=300)
    except Exception:
        return [], "context"
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return [], "context"
    try:
        payload = json.loads(match.group(0))
        qs = payload.get("queries", [])
        variants = [q for q in qs if isinstance(q, str) and q.strip()][:2]
        style = payload.get("style")
        return variants, (style if style in {"attribute", "context"} else "context")
    except Exception:
        return [], "context"


def _trim_chunk_lines(content: str, query_words: set[str], max_lines: int) -> str:
    lines = [ln for ln in content.splitlines() if ln.strip()]
    if len(lines) <= max_lines:
        return content
    scored = []
    for i, ln in enumerate(lines):
        lw = {w for w in re.sub(r"[^a-z0-9 ]", " ", ln.lower()).split() if len(w) > 2}
        overlap = len(lw & query_words)
        scored.append((overlap, i, ln))
    top = sorted(range(len(lines)), key=lambda i: (-scored[i][0], scored[i][1]))[:max_lines]
    return "\n".join(lines[i] for i in sorted(top))


async def run_search(query: str, options: list[str] | None, user_id: str, top_k: int) -> list[dict]:
    extra_variants, qstyle = await expand_query(query)
    variants = [query] + extra_variants
    if options:
        variants[0] = query + "\n" + "\n".join(options)
    vec_lists = await llm.embed(variants)
    qvecs = [np.asarray(v, dtype=np.float32) for v in vec_lists]

    matrix, ids = vec_table.get(user_id)
    best_sim: dict[str, float] = {}
    per_variant_hits: list[list[str]] = []
    for qv in qvecs:
        hits = cosine_top(matrix, ids, qv, VECTOR_CANDIDATES)
        per_variant_hits.append(hits)
        id_pos = {fid: i for i, fid in enumerate(ids)}
        for fid in hits:
            row = matrix[id_pos[fid]]
            sim = float(np.dot(row, qv)) / ((np.linalg.norm(row) + 1e-9) * (np.linalg.norm(qv) + 1e-9))
            if sim > best_sim.get(fid, -1e9):
                best_sim[fid] = sim

    kw_ids = [fid for fid, _ in keyword_search(user_id, query, KEYWORD_CANDIDATES)]
    kw2_ids = [fid for fid, _ in keyword_search(user_id, variants[-1], KEYWORD_CANDIDATES)]
    fused_ids = _rrf_fuse([*per_variant_hits, kw_ids, kw2_ids])

    prof = get_rollup(user_id, "__profile__")
    if prof:
        fused_ids = [prof["id"]] + [f for f in fused_ids if f != prof["id"]]

    if not fused_ids:
        return []

    contents = fetch_contents(fused_ids)
    active = [fid for fid in fused_ids if not contents.get(fid, {}).get("superseded_by")]
    stale = [fid for fid in fused_ids if contents.get(fid, {}).get("superseded_by")]

    if len(active) > 12:
        head = active[:48]
        order = await rerank_passages(query, [contents[f]["content"][:200] for f in head])
        if order:
            head_set = set(order)
            active = [head[i] for i in order] + [f for f in head if head.index(f) not in head_set] + active[48:]

    if prof:
        active = [prof["id"]] + [f for f in active if f != prof["id"]]

    if not CHUNKS_ENABLED or qstyle == "attribute_never":
        active = [f for f in active if contents.get(f, {}).get("kind") != "chunk"]

    trimmed = (active + stale)[:top_k]

    results = []
    query_words = {w for w in re.sub(r"[^a-z0-9 ]", " ", (query + " " + " ".join(variants)).lower()).split() if len(w) > 2}
    for fid in trimmed:
        info = contents.get(fid)
        if info is None:
            continue
        out_content = info["content"]
        if TRIM_CHUNK_LINES > 0 and info.get("kind") == "chunk":
            out_content = _trim_chunk_lines(out_content, query_words, TRIM_CHUNK_LINES)
        results.append(
            {
                "id": fid,
                "content": out_content,
                "score": round(best_sim.get(fid, 0.0), 4),
                "created_at": info["created_at"],
            }
        )
    return results
