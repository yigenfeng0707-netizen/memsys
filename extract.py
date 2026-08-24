import json
import re

from llm import llm

EXTRACT_SYSTEM = """You extract durable long-term memories from a slice of a multi-session dialogue between a user and an assistant.

Output STRICT JSON only, no markdown fences: {"facts": [{"content": str, "kind": "fact"|"preference"|"event"|"relation"|"rule", "timestamp": int|null, "topic": str}]}

Rules:
- content: one self-contained atomic statement in third person, preserving exact names, places, numbers and dates from the dialogue. Resolve pronouns using the surrounding conversation.
- kind: fact (stable attribute), preference (likes/dislikes/favorites), event (significant happening or plan), relation (tie between people), rule (explicit instruction to remember).
- topic: 1-3 word lowercase category for aggregation, e.g. "camping", "career", "family", "pets", "food", "travel", "health". Reuse the same wording for the same theme.
- timestamp: the most specific Unix-millisecond time the statement refers to. Anchor relative expressions like "yesterday", "last month", "next year" on the message timestamps provided in the slice. null if unclear.
- Never invent information. Skip small talk, transient states ("I'm tired today"), and assistant small talk replies.
- Do not output two facts that say the same thing; merge them into one.
- Maximum 20 facts. Fewer, high-quality facts are better."""

CONFLICT_SYSTEM = """You compare two long-term memory statements about the same people and topics, and decide whether the NEW statement makes the OLD one outdated.

Decide exactly one label:
- OUTDATED: they describe the same attribute or topic of the same subject but differ in value, state, location or time frame, and the NEW one reflects a later change (moved city, changed job, new favorite, ended relationship).
- RELATED: similar topics but both can stay true at once (different facets, different people, general vs specific).
- DUPLICATE: the NEW one restates the OLD one with no new information.

Output STRICT JSON only: {"label": "OUTDATED"|"RELATED"|"DUPLICATE"}"""


def _parse_json(raw: str) -> dict | None:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


async def extract_facts(text: str, known_context: str | None = None) -> list[dict]:
    user_msg = f"<dialogue_slice>\n{text}\n</dialogue_slice>"
    if known_context:
        user_msg = (
            f"KNOWN CONTEXT about the people (use these exact names in facts, never 'the user' or 'the assistant'):\n"
            f"{known_context}\n\n{user_msg}"
        )
    raw = None
    try:
        raw = await llm.chat(EXTRACT_SYSTEM, user_msg, max_tokens=1500)
    except Exception:
        return []
    out = _parse_extracted(raw)
    if not out and len(text) > 300:
        try:
            raw2 = await llm.chat(
                EXTRACT_SYSTEM,
                user_msg,
                max_tokens=1500,
                temperature=0.3,
            )
        except Exception:
            return []
        out = _parse_extracted(raw2)
    return out


def _parse_extracted(raw: str) -> list[dict]:
    payload = _parse_json(raw)
    if not payload:
        return []
    out = []
    for f in payload.get("facts", []):
        content = (f.get("content") or "").strip()
        if not content:
            continue
        ts = f.get("timestamp")
        topic_raw = f.get("topic")
        topic = topic_raw.strip().lower()[:40] if isinstance(topic_raw, str) and topic_raw.strip() else "general"
        out.append(
            {
                "content": content,
                "kind": f.get("kind") if f.get("kind") in {"fact", "preference", "event", "relation", "rule"} else "fact",
                "timestamp": ts if isinstance(ts, int) else None,
                "topic": topic,
            }
        )
    return out[:20]


RERANK_SYSTEM = """You select dialogue-memory passages relevant to a question.

Given numbered passages, identify EVERY passage that contains information needed to answer or contextualize the question, including partial evidence and background facts about mentioned people.

Output STRICT JSON only: {"top": [numbers]} - passage numbers ordered most-relevant-first. Include all helpful passages; exclude clearly irrelevant ones."""


async def rerank_passages(question: str, passages: list[str]) -> list[int] | None:
    lines = "\n".join(f"[{i+1}] {p}" for i, p in enumerate(passages))
    try:
        raw = await llm.chat(
            RERANK_SYSTEM,
            f"Question: {question}\n\nPassages:\n{lines}",
            max_tokens=300,
        )
    except Exception:
        return None
    payload = _parse_json(raw)
    if not payload:
        return None
    top = payload.get("top")
    if not isinstance(top, list):
        return None
    out = []
    for x in top:
        if isinstance(x, int) and 1 <= x <= len(passages) and (x - 1) not in out:
            out.append(x - 1)
        elif isinstance(x, str) and x.strip().isdigit():
            xi = int(x)
            if 1 <= xi <= len(passages) and (xi - 1) not in out:
                out.append(xi - 1)
    return out


PROFILE_SYSTEM = """You maintain ONE compact profile card summarizing a user's stable attributes, built from long-term dialogue memories.

Input: CURRENT PROFILE (may be empty) and NEW FACTS.
Merge the new facts into the profile. Output STRICT JSON only: {"summary": "..."}.

Profile format - short bullet lines, each one stable attribute:
- Identity: name, home city, occupation
- Family and pets
- Hobbies and activities: list EVERY distinct one mentioned across all inputs
- Favorites: food, music, colors, etc.
- Possessions and significant events with dates

Rules:
- Keep EVERY distinct attribute already in the CURRENT PROFILE unless a NEW fact explicitly replaces it (moved city, changed job); then keep only the latest value with its date.
- For lists (hobbies, favorites), always carry over every known item.
- Preserve exact names, places, numbers, dates. Never invent anything.
- Maximum 220 words."""


async def merge_profile(current: str | None, new_facts: list[str]) -> str | None:
    user = (
        f"CURRENT PROFILE:\n{current if current else '(empty)'}\n\n"
        f"NEW FACTS:\n" + "\n".join(f"- {t}" for t in new_facts)
    )
    try:
        raw = await llm.chat(PROFILE_SYSTEM, user, max_tokens=700)
    except Exception:
        return None
    payload = _parse_json(raw)
    if not payload:
        return None
    summary = (payload.get("summary") or "").strip()
    return summary or None


ROLLUP_SYSTEM = """You maintain a compact topic-summary memory for one user.

Input: the CURRENT summary (may be empty) and NEW facts learned about the same topic.
Output STRICT JSON only: {"summary": "..."} where summary merges the new facts into the current one.

Rules:
- Compact bullet-style lines, at most 120 words.
- Keep every distinct item already present unless a NEW fact explicitly replaces or contradicts it; then keep only the latest value (dates matter, preserve them).
- Preserve exact names, places, numbers and dates.
- Never invent anything not supported by the inputs."""


async def merge_rollup(current: str | None, new_facts: list[str]) -> str | None:
    user = (
        f"CURRENT SUMMARY:\n{current if current else '(empty)'}\n\n"
        f"NEW FACTS:\n" + "\n".join(f"- {t}" for t in new_facts)
    )
    try:
        raw = await llm.chat(ROLLUP_SYSTEM, user, max_tokens=500)
    except Exception:
        return None
    payload = _parse_json(raw)
    if not payload:
        return None
    summary = (payload.get("summary") or "").strip()
    return summary or None


async def judge_conflict(old_text: str, new_text: str) -> str:
    try:
        raw = await llm.chat(
            CONFLICT_SYSTEM,
            f"OLD memory: {old_text}\n\nNEW memory: {new_text}",
            max_tokens=100,
            temperature=0.0,
        )
    except Exception:
        return "RELATED"
    payload = _parse_json(raw)
    if not payload:
        return "RELATED"
    label = payload.get("label")
    return label if label in {"OUTDATED", "RELATED", "DUPLICATE"} else "RELATED"
