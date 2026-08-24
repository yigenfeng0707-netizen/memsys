import os
import sqlite3
import sys
import time

import httpx

BASE = os.environ.get("MEMSYS_TEST_BASE", "http://127.0.0.1:8790")
DB = os.environ.get("MEMSYS_TEST_DB", os.path.join(os.path.dirname(__file__), "data", "memories.db"))

failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail and not cond else ""))
    if not cond:
        failures.append(name)


def main() -> int:
    client = httpx.Client(timeout=600)
    uid = f"eval:govtest:{int(time.time())}"
    t0 = 1672531200000

    s1 = [
        {"role": "user", "timestamp": t0, "content": "Hi! I'm Alice. I live in Stockholm, Sweden with my dog Robo."},
        {"role": "assistant", "content": "Nice to meet you Alice!"},
        {"role": "user", "timestamp": t0 + 60000, "content": "I work as a dentist at the city clinic. In my free time I play badminton."},
        {"role": "assistant", "content": "A balanced life! How long have you played badminton?"},
        {"role": "user", "timestamp": t0 + 120000, "content": "About five years now. My favorite food is Thai curry."},
    ]

    t1 = 1735689600000
    s2 = [
        {"role": "user", "timestamp": t1, "content": "Big news - we moved to Oslo, Norway last month! The dog loves the new place."},
        {"role": "assistant", "content": "Congratulations on the move to Oslo!"},
        {"role": "user", "timestamp": t1 + 60000, "content": "I also changed jobs. I'm a dental consultant now, no more clinic work."},
    ]

    r1 = client.post(f"{BASE}/add", json={"request_id": f"{uid}:c0", "messages": s1, "user_id": uid, "session_id": f"{uid}:s0"})
    check("add session-1 ok", r1.status_code == 200)
    r2 = client.post(f"{BASE}/add", json={"request_id": f"{uid}:c1", "messages": s2, "user_id": uid, "session_id": f"{uid}:s1"})
    check("add session-2 ok", r2.status_code == 200)

    con = sqlite3.connect(DB)
    rows = con.execute(
        "SELECT kind, COUNT(*), SUM(CASE WHEN superseded_by IS NOT NULL THEN 1 ELSE 0 END) FROM memories WHERE user_id=? GROUP BY kind",
        (uid,),
    ).fetchall()
    kinds = {r[0]: (r[1], r[2] or 0) for r in rows}
    print(f"    memory kinds: {kinds}")
    extracted_total = sum(v[0] for k, v in kinds.items() if k != "chunk")
    check("facts extracted", extracted_total >= 3, str(kinds))
    check("supersede chain exists", any(v[1] > 0 for v in kinds.values()))

    def search(query: str) -> list[str]:
        resp = client.post(f"{BASE}/search", json={"query": query, "user_id": uid, "top_k": 100})
        return [d["content"] for d in resp.json().get("data", [])]

    current = search("Where does Alice live now?")
    joined = "\n".join(current)
    check("current-city query hits Oslo", "Oslo" in joined, joined[:150])

    past = search("Where did Alice live in 2023?")
    all_past = "\n".join(past)
    check("temporal query still finds Stockholm", "Stockholm" in all_past)

    job = search("What is Alice's job?")
    all_jobs = "\n".join(job)
    check("job query surfaces consultant", "consultant" in all_jobs.lower(), all_jobs[:200])

    print()
    if failures:
        print(f"FAILED: {len(failures)} -> {failures}")
        return 1
    print("ALL GOVERNANCE TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
