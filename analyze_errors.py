import asyncio
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import httpx

DATA_PATH = Path(__file__).resolve().parent / "eval_data" / "locomo10.json"
RUNS_DIR = Path(__file__).resolve().parent.parent / "eval_runs"
API = "http://127.0.0.1:8790"


def norm_words(text: str) -> list[str]:
    return re.sub(r"[^a-z0-9 ]", " ", text.lower()).split()


def ngrams(words: list[str], n: int = 6) -> set[tuple]:
    return {tuple(words[i : i + n]) for i in range(len(words) - n + 1)}


def evidence_covered(evidence_texts: list[str], memory_texts: list[str]) -> bool:
    mem_ngrams: set[tuple] = set()
    for mt in memory_texts:
        w = norm_words(mt)
        mem_ngrams |= ngrams(w, 6)
    if not mem_ngrams:
        return False
    for et in evidence_texts:
        ew = norm_words(et)
        ev_grams = ngrams(ew, 6)
        if ev_grams and (ev_grams & mem_ngrams):
            return True
    return False


async def main_async() -> int:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    stats = defaultdict(lambda: {"miss": 0, "answ": 0})
    async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=10)) as client:
        sem = asyncio.Semaphore(6)

        async def probe(ci: int, idx: int, qa: dict):
            sample_id = str(data[ci].get("sample_id", ci))
            async with sem:
                resp = await client.post(
                    f"{API}/search",
                    json={"query": qa["question"], "user_id": f"locomo:{sample_id}", "top_k": 100},
                )
            mems = [d["content"] for d in resp.json().get("data", [])]
            ev_texts = []
            cv = data[ci]["conversation"]
            for did in qa.get("evidence", []):
                for i in range(1, 40):
                    sess = cv.get(f"session_{i}")
                    if isinstance(sess, list):
                        for t in sess:
                            if isinstance(t, dict) and t.get("dia_id") == did:
                                ev_texts.append(t.get("text", ""))
            covered = evidence_covered(ev_texts, mems)
            return ci, qa.get("category"), covered

        tasks = []
        for ci in range(10):
            p = RUNS_DIR / f"conv{ci}_results.jsonl"
            if not p.exists():
                continue
            rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
            for r in rows:
                if r.get("skipped_no_gold") or r["is_correct"]:
                    continue
                idx = int(r["qid"].split(":")[1])
                tasks.append(probe(ci, idx, data[ci]["qa"][idx]))

        done = await asyncio.gather(*tasks)

    for ci, cat, covered in done:
        key = stats[cat]
        if covered:
            key["answ"] += 1
        else:
            key["miss"] += 1

    total_miss = sum(s["miss"] for s in stats.values())
    total_answ = sum(s["answ"] for s in stats.values())
    names = {1: "single-hop", 2: "multi-hop", 3: "temporal", 4: "open-domain", 5: "adversarial"}
    print(f"wrong answers analyzed: {total_miss + total_answ}")
    print(f"retrieval MISS (evidence NOT in top100): {total_miss} ({total_miss/(total_miss+total_answ)*100:.0f}%)")
    print(f"answer FAIL (evidence was retrieved):    {total_answ} ({total_answ/(total_miss+total_answ)*100:.0f}%)")
    print()
    for cat in sorted(stats):
        s = stats[cat]
        t = s["miss"] + s["answ"]
        print(f"  cat{cat} {names.get(cat,''):<12}: miss {s['miss']/t*100:4.0f}% ({s['miss']:3}) | answer-fail {s['answ']/t*100:4.0f}% ({s['answ']:3})")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main_async()))
