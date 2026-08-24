import argparse
import asyncio
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR.parent))

from config import LLM_API_KEY, LLM_BASE_URL

DATA_PATH = BASE_DIR / "eval_data" / "locomo10.json"
RUNS_DIR = BASE_DIR.parent / "eval_runs"
DATA: list = []

ANSWER_MODEL = "gpt-4o-mini"
JUDGE_MODEL = "gpt-4o"
TOP_K = 100

OPEN_ENDED_ANSWER_TEMPLATE = """You are asked to answer a question based on your memories of a conversation.

<instructions>
1. Use only the provided memories. Prefer the memory that answers the question most directly.
2. Your memories are episodic raw observations. Reason about what they imply. Do not refuse just because the answer is not stated verbatim.
3. The question may contain typos. Match it to the most relevant memory even if the wording differs.
4. When multiple answers are possible, list all supported answers, not just the first.
5. For counts or time intervals, enumerate carefully before answering.
6. Preserve specific names, titles, places, and labels from the memories. Use "Rob" not "a colleague", "Sweden" not "home country".
7. Convert relative times like "yesterday", "last month", and "last year" into dates, months, or years when the memory timestamp makes it clear. Keep week-based expressions relative.
8. If memories conflict, prefer the most recent supported memory.
9. For list questions, include all required items and no extras.
10. Keep the final answer minimal. Do not add explanation, background, or extra dates unless needed for correctness.
</instructions>

<memories>
Memories for user {{speaker_1_name}}:

{{speaker_1_memories}}

Memories for user {{speaker_2_name}}:

{{speaker_2_memories}}
</memories>

Question: {{question}}
Answer with the shortest correct phrase or sentence. No preamble, no fluff:"""

ACCURACY_PROMPT = """Your task is to label an answer as CORRECT or WRONG given:
(1) a question,
(2) a gold (ground truth) answer,
(3) a generated answer.

Core principle - Inclusion + Non-contradiction
- Be GENEROUS: if the generated answer clearly includes the gold's key content (or a clear paraphrase of the same content) and does not contradict it, mark CORRECT - even if extra details are added.
- Mark WRONG only when the generated answer does not include the gold's content, changes it, or contradicts it.

TIME (strict granularity; relative form equivalence; no calendar math)
- Granularity must match exactly: HOUR<->HOUR, DAY<->DAY, MONTH<->MONTH, YEAR<->YEAR.
  Do not answer a gold at a different time unit - even if the numeric value overlaps. Do not answer a month-level gold with a specific day, nor a year with a specific month/day/hour, etc.
- Do NOT convert relative <-> absolute. If the gold uses a relative time expression, the generated answer must also use a relative form (or a clear paraphrase of that same form), not a computed date/range.
- Treat harmless modifiers in relative forms as equivalent when both the anchor date and the time unit are the same.

- Lists of DISTINCT facts:
- If the gold answer lists multiple distinct facts (joined by "and", commas, or slashes), the generated answer must cover **all** of them.
- Extra non-contradictory items **generally count as WRONG**.
    - Example: gold = A, B, C ; gen = A, B, C -> CORRECT
    - Example: gold = A, B, C ; gen = A, B, C, D -> WRONG
- Exception: If a gold element is elaborated or split into finer details in the generated answer, it is still considered CORRECT.

Preference/Benefit Questions (e.g., "what X likes/values most")
- If gold lists multiple reasons/aspects, the generated answer only needs to include **any one** of them without contradiction to be CORRECT.

Now it's time for the real question:
Question: {question}
Gold answer: {gold_answer}
Generated answer: {generated_answer}

First, provide a short (one sentence) explanation of your reasoning, then finish with CORRECT or WRONG.
Do NOT include both CORRECT and WRONG in your response, or it will break the evaluation script.

Just return the label CORRECT or WRONG in a json format with the key as "label":

```json
{{
    "label": "CORRECT" or "WRONG"
}}
```"""


def parse_dt_ms(s: str) -> int | None:
    try:
        dt = datetime.strptime(s.strip(), "%I:%M %p on %d %B, %Y")
        return int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
    except Exception:
        return None


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def append_jsonl(path: Path, obj: dict) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False) + "\n")


def render_template(template: str, values: dict) -> str:
    return re.sub(
        r"\{\{(\w+)\}\}",
        lambda m: str(values.get(m.group(1), "")),
        template,
    )


def render_judge(template: str, values: dict) -> str:
    return re.sub(
        r"\{(question|gold_answer|generated_answer)\}",
        lambda m: str(values[m.group(1)]),
        template,
    )


class LLM:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def complete(self, model: str, prompt: str, max_tokens: int = 512) -> str:
        for attempt in range(3):
            try:
                resp = await self.client.post(
                    f"{LLM_BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {LLM_API_KEY}"},
                    json={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0, "max_tokens": max_tokens},
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"].strip()
            except Exception:
                if attempt == 2:
                    raise
                await asyncio.sleep(2 * (attempt + 1))
        raise RuntimeError("unreachable")


def split_by_speaker(content: str, spk_a: str, spk_b: str) -> tuple[str, str]:
    a_lines, b_lines = [], []
    for line in content.splitlines():
        if line.startswith(spk_a + ":"):
            a_lines.append(line)
        elif line.startswith(spk_b + ":"):
            b_lines.append(line)
        elif line.startswith("["):
            body = line.split("] ", 1)[-1]
            if body.startswith(spk_a + ":"):
                a_lines.append(line)
            elif body.startswith(spk_b + ":"):
                b_lines.append(line)
            else:
                b_lines.append(line)
        else:
            b_lines.append(line)
    return "\n".join(a_lines), "\n".join(b_lines)


async def ingest_conversation(client: httpx.AsyncClient, conv: dict, sample_id: str) -> None:
    cv = conv["conversation"]
    spk_a = cv["speaker_a"]
    spk_b = cv["speaker_b"]
    n_sessions = 0
    for i in range(1, 60):
        sess = cv.get(f"session_{i}")
        if not isinstance(sess, list):
            continue
        dt_raw = cv.get(f"session_{i}_date_time")
        ts = parse_dt_ms(dt_raw) if dt_raw else None
        messages = [
            {"role": t["speaker"], "content": t["text"], "timestamp": ts}
            for t in sess
            if isinstance(t, dict) and (t.get("text") or "").strip()
        ]
        if not messages:
            continue
        rid = f"locomo:{sample_id}:session_{i}"
        resp = await client.post(
            "http://127.0.0.1:8790/add",
            json={"request_id": rid, "messages": messages, "user_id": f"locomo:{sample_id}", "session_id": rid},
        )
        resp.raise_for_status()
        n_sessions += 1
    print(f"[ingest] {sample_id}: {n_sessions} sessions done")


async def answer_and_judge(client: httpx.AsyncClient, llm: LLM, sem: asyncio.Semaphore, qa_list, sample_id, spk_a, spk_b, out_answers: Path, out_results: Path):
    done_ans = {r["qid"] for r in load_jsonl(out_answers)}
    done_res = {r["qid"] for r in load_jsonl(out_results)}

    async def one(idx: int, qa: dict):
        qid = f"{sample_id}:{idx}"
        if qid in done_res:
            return None
        question = qa["question"]
        gold = str(qa.get("answer", "") or "")
        async with sem:
            if qid not in done_ans:
                sr = await client.post(
                    "http://127.0.0.1:8790/search",
                    json={"query": question, "user_id": f"locomo:{sample_id}", "top_k": TOP_K},
                )
                sr.raise_for_status()
                data = sr.json().get("data", [])
                a_mem, b_mem = [], []
                for d in data:
                    sa, sb = split_by_speaker(d["content"], spk_a, spk_b)
                    if sa:
                        a_mem.append(sa)
                    if sb:
                        b_mem.append(sb)
                prompt = render_template(
                    OPEN_ENDED_ANSWER_TEMPLATE,
                    {
                        "speaker_1_name": spk_a,
                        "speaker_1_memories": "\n\n".join(a_mem) or "(none)",
                        "speaker_2_name": spk_b,
                        "speaker_2_memories": "\n\n".join(b_mem) or "(none)",
                        "question": question,
                    },
                )
                generated = await llm.complete(ANSWER_MODEL, prompt, max_tokens=256)
                append_jsonl(out_answers, {"qid": qid, "question": question, "generated": generated})
            else:
                generated = next(r["generated"] for r in load_jsonl(out_answers) if r["qid"] == qid)

            if not gold.strip():
                row = {"qid": qid, "label": "SKIP", "is_correct": False, "category": qa.get("category"), "skipped_no_gold": True}
                append_jsonl(out_results, row)
                return row

            jp = render_judge(
                ACCURACY_PROMPT,
                {"question": question, "gold_answer": gold, "generated_answer": generated},
            )
            raw = await llm.complete(JUDGE_MODEL, jp, max_tokens=200)
            label = "WRONG"
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                try:
                    label = str(json.loads(m.group(0)).get("label", "WRONG")).upper()
                except Exception:
                    pass
            row = {"qid": qid, "label": label, "is_correct": label == "CORRECT", "category": qa.get("category")}
            append_jsonl(out_results, row)
            return row

    tasks = [one(i, qa) for i, qa in enumerate(qa_list)]
    rows = [r for r in await asyncio.gather(*tasks) if r]
    return rows


async def ingest_one(client: httpx.AsyncClient, ci: int) -> tuple[str, float]:
    c = DATA[ci]
    sample_id = str(c.get("sample_id", ci))
    t0 = time.time()
    await ingest_conversation(client, c, sample_id)
    return sample_id, time.time() - t0


async def ingest_phase(client: httpx.AsyncClient, conv_indices: list[int], workers: int) -> None:
    sem = asyncio.Semaphore(workers)

    async def guarded(ci: int):
        async with sem:
            return await ingest_one(client, ci)

    rows = await asyncio.gather(*[guarded(ci) for ci in conv_indices])
    for sample_id, secs in rows:
        print(f"[ingest] {sample_id}: done in {secs:.0f}s")


async def qa_phase(client: httpx.AsyncClient, llm: LLM, conv_indices: list[int], limit: int | None) -> None:
    sem = asyncio.Semaphore(6)
    for ci in conv_indices:
        c = DATA[ci]
        sample_id = str(c.get("sample_id", ci))
        cv = c["conversation"]
        out_answers = RUNS_DIR / f"conv{ci}_answers.jsonl"
        out_results = RUNS_DIR / f"conv{ci}_results.jsonl"
        qa_list = c["qa"][:limit] if limit else c["qa"]
        t1 = time.time()
        await answer_and_judge(client, llm, sem, qa_list, sample_id, cv["speaker_a"], cv["speaker_b"], out_answers, out_results)
        print(f"[qa] conv{ci} ({sample_id}) done in {time.time()-t1:.0f}s")


def aggregate(conv_indices: list[int]) -> int:
    results = []
    for ci in conv_indices:
        p = RUNS_DIR / f"conv{ci}_results.jsonl"
        results.extend([r for r in load_jsonl(p) if not r.get("skipped_no_gold")])
    if not results:
        print("no results")
        return 1
    overall = sum(r["is_correct"] for r in results) / len(results)
    print(f"\n==== AGGREGATE ({len(results)} questions) ====")
    print(f"Overall accuracy: {overall*100:.1f}%")
    by_cat: dict[int, list] = {}
    for r in results:
        by_cat.setdefault(r["category"], []).append(r["is_correct"])
    cat_names = {1: "single-hop", 2: "multi-hop", 3: "temporal", 4: "open-domain", 5: "adversarial"}
    for cat in sorted(by_cat):
        vals = by_cat[cat]
        print(f"  cat{cat} {cat_names.get(cat,''):<12}: {sum(vals)/len(vals)*100:5.1f}%  (n={len(vals)})")
    return 0


async def main_async() -> int:
    global DATA
    ap = argparse.ArgumentParser()
    ap.add_argument("--conv", type=int, default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--skip-ingest", action="store_true")
    ap.add_argument("--skip-qa", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    args_cli = ap.parse_args()

    DATA = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    conv_indices = [args_cli.conv] if args_cli.conv is not None else list(range(len(DATA)))

    RUNS_DIR.mkdir(exist_ok=True)

    async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=15)) as client, httpx.AsyncClient(timeout=httpx.Timeout(120, connect=15)) as llm_http:
        llm = LLM(llm_http)
        if not args_cli.skip_ingest:
            await ingest_phase(client, conv_indices, args_cli.workers)
        if not args_cli.skip_qa:
            await qa_phase(client, llm, conv_indices, args_cli.limit)

    return aggregate(conv_indices)


if __name__ == "__main__":
    sys.exit(asyncio.run(main_async()))
