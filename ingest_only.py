import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import httpx

import eval_locomo
from eval_locomo import DATA_PATH, RUNS_DIR, ingest_phase


async def main_async() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    eval_locomo.DATA = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    RUNS_DIR.mkdir(exist_ok=True)
    async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=15)) as client:
        await ingest_phase(client, list(range(len(eval_locomo.DATA))), args.workers)
    print("INGEST COMPLETE")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main_async()))
