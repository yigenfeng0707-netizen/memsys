import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import httpx

import eval_locomo
from eval_locomo import DATA_PATH, ingest_phase


async def main_async() -> int:
    eval_locomo.DATA = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=15)) as client:
        await ingest_phase(client, list(range(1, len(eval_locomo.DATA))), 4)
    print("INGEST COMPLETE 1-9")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main_async()))
