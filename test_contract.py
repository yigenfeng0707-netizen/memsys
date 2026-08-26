import os
import sys
import time

import httpx

BASE = os.environ.get("MEMSYS_TEST_BASE", "http://127.0.0.1:8790")
TOKEN = os.environ.get("MEMSYS_TEST_TOKEN", "")

failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f"  ({detail})" if detail and not cond else ""))
    if not cond:
        failures.append(name)


def main() -> int:
    headers = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}
    client = httpx.Client(timeout=60, headers=headers)

    r = client.get(f"{BASE}/health")
    check("health 2xx", 200 <= r.status_code < 300, str(r.status_code))

    uid = f"eval:selftest:{int(time.time())}"
    sid = f"{uid}:session-0"
    rid = f"{uid}:chunk-0"

    add_body = {
        "request_id": rid,
        "messages": [
            {"role": "user", "timestamp": 1704067200000, "content": "Hi, my name is Alice and I live in Sweden."},
            {"role": "assistant", "content": "Nice to meet you, Alice! How is the weather in Sweden?"},
            {"role": "user", "content": "It is rainy. By the way, my dog Robo loves playing in the park."},
        ],
        "user_id": uid,
        "session_id": sid,
    }
    r = client.post(f"{BASE}/add", json=add_body)
    check("add 200", r.status_code == 200, r.text[:200])
    payload = r.json()
    check("add success true", payload.get("success") is True)
    check("add echoes request_id", payload.get("request_id") == rid)
    check("add echoes user_id", payload.get("user_id") == uid)
    check("add echoes session_id", payload.get("session_id") == sid)

    r2 = client.post(f"{BASE}/add", json=add_body)
    check("add idempotent replay 200", r2.status_code == 200 and r2.json().get("success") is True)

    q = "Where does Alice live?"
    sr = client.post(f"{BASE}/search", json={"query": q, "user_id": uid, "top_k": 5})
    check("search 200", sr.status_code == 200, sr.text[:200])
    sdata = sr.json().get("data")
    check("search data is list", isinstance(sdata, list))
    if isinstance(sdata, list) and sdata:
        first = sdata[0]
        check("item has id str", isinstance(first.get("id"), str) and len(first["id"]) > 0)
        check("item has content str", isinstance(first.get("content"), str) and len(first["content"]) > 0)
        check("top hit relevant (Sweden)", "Sweden" in "".join(d["content"] for d in sdata))
    else:
        check("search returned hits", False, sr.text[:200])

    other = client.post(f"{BASE}/search", json={"query": q, "user_id": uid + "-other", "top_k": 5})
    check("isolation empty for other user", other.json().get("data") == [])

    mc = client.post(
        f"{BASE}/search",
        json={
            "query": "Which answer best matches the memory?",
            "options": ["A. Alice lives in Norway", "B. Alice lives in Sweden"],
            "user_id": uid,
            "top_k": 100,
        },
    )
    check("mc search 200", mc.status_code == 200)
    check("top_k=100 respected", len(mc.json().get("data", [])) <= 100)

    print()
    if failures:
        print(f"FAILED: {len(failures)} -> {failures}")
        return 1
    print("ALL CONTRACT TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
