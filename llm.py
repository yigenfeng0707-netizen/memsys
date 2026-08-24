import asyncio

import httpx

from config import (
    CHAT_MODEL,
    DISABLE_THINKING,
    EMBED_API_KEY,
    EMBED_BASE_URL,
    EMBED_MODEL,
    LLM_API_KEY,
    LLM_BASE_URL,
)


def _should_disable_thinking() -> bool:
    if DISABLE_THINKING == "1":
        return True
    if DISABLE_THINKING == "0":
        return False
    return "sensenova" in CHAT_MODEL.lower()


class LLMClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=LLM_BASE_URL,
            headers={"Authorization": f"Bearer {LLM_API_KEY}"},
            timeout=httpx.Timeout(90.0, connect=15.0),
        )
        self._embed_client = httpx.AsyncClient(
            base_url=EMBED_BASE_URL,
            headers={"Authorization": f"Bearer {EMBED_API_KEY}"},
            timeout=httpx.Timeout(60.0, connect=15.0),
        )

    async def chat(self, system: str, user: str, temperature: float = 0.0, max_tokens: int = 2048) -> str:
        payload = {
            "model": CHAT_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if _should_disable_thinking():
            payload["thinking"] = {"type": "disabled"}
        for attempt in range(3):
            try:
                resp = await self._client.post("/chat/completions", json=payload)
                resp.raise_for_status()
                message = resp.json()["choices"][0]["message"]
                content = (message.get("content") or "").strip()
                if content:
                    return content
                reasoning = (message.get("reasoning") or message.get("reasoning_content") or "").strip()
                if reasoning and attempt < 2:
                    payload["max_tokens"] = int(payload["max_tokens"] * 2)
                    continue
                return reasoning
            except (httpx.HTTPError, KeyError):
                if attempt == 2:
                    raise
                await asyncio.sleep(1.5 * (attempt + 1))
        raise RuntimeError("unreachable")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), 32):
            batch = texts[i : i + 32]
            for attempt in range(3):
                try:
                    resp = await self._embed_client.post(
                        "/embeddings",
                        json={"model": EMBED_MODEL, "input": batch},
                    )
                    resp.raise_for_status()
                    data = sorted(resp.json()["data"], key=lambda d: d["index"])
                    out.extend(d["embedding"] for d in data)
                    break
                except (httpx.HTTPError, KeyError):
                    if attempt == 2:
                        raise
                    await asyncio.sleep(1.5 * (attempt + 1))
        return out


llm = LLMClient()
