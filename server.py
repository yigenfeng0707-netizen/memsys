from typing import Any, Literal, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

from config import AUTH_TOKEN
from pipeline import run_add, run_search

app = FastAPI(title="MemSys", version="0.1.0")


class Message(BaseModel):
    role: str
    content: str = Field(min_length=1)
    timestamp: Optional[int] = None


class AddRequest(BaseModel):
    request_id: str = Field(min_length=1)
    messages: list[Message]
    user_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)

    model_config = {"extra": "ignore"}


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    options: Optional[list[str]] = None
    user_id: str = Field(min_length=1)
    top_k: int = Field(gt=0)

    model_config = {"extra": "ignore"}


def check_auth(authorization: Optional[str], x_api_key: Optional[str]) -> None:
    if not AUTH_TOKEN:
        return
    supplied = ""
    if authorization and authorization.lower().startswith("bearer "):
        supplied = authorization[7:].strip()
    elif authorization:
        supplied = authorization.strip()
    elif x_api_key:
        supplied = x_api_key.strip()
    if supplied != AUTH_TOKEN:
        raise HTTPException(status_code=401, detail={"reason": "invalid credentials"})


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/debug/search")
async def debug_search(q: str, user_id: str) -> dict:
    import traceback
    steps: dict[str, Any] = {}
    try:
        from pipeline import expand_query, cosine_top, _rrf_fuse, keyword_search as kws
        from store import vec_table, fetch_contents
        import numpy as np
        from llm import llm
        variants = [q]
        try:
            extra, style = await expand_query(q)
            variants += extra
            steps["expand"] = {"ok": True, "variants": variants, "style": style}
        except Exception as exc:
            steps["expand"] = {"ok": False, "err": f"{type(exc).__name__}: {exc}", "tb": traceback.format_exc()[-500:]}
        try:
            vecs = await llm.embed(variants)
            steps["embed"] = {"ok": True, "n": len(vecs), "dim": len(vecs[0]) if vecs else 0}
        except Exception as exc:
            steps["embed"] = {"ok": False, "err": f"{type(exc).__name__}: {exc}", "tb": traceback.format_exc()[-500:]}
        try:
            matrix, ids = vec_table.get(user_id)
            steps["vectors"] = {"ok": True, "rows": int(matrix.shape[0])}
        except Exception as exc:
            steps["vectors"] = {"ok": False, "err": f"{type(exc).__name__}: {exc}", "tb": traceback.format_exc()[-500:]}
        try:
            kw = kws(user_id, q, 50)
            steps["fts"] = {"ok": True, "hits": len(kw)}
        except Exception as exc:
            steps["fts"] = {"ok": False, "err": f"{type(exc).__name__}: {exc}", "tb": traceback.format_exc()[-500:]}
        try:
            data = await run_search(q, None, user_id, 25)
            steps["full_search"] = {"ok": True, "hits": len(data)}
        except Exception as exc:
            steps["full_search"] = {"ok": False, "err": f"{type(exc).__name__}: {exc}", "tb": traceback.format_exc()[-1500:]}
    except Exception as exc:
        steps["outer"] = {"ok": False, "err": str(exc)}
    return steps


@app.post("/add")
async def add(req: AddRequest, authorization: Optional[str] = Header(None), x_api_key: Optional[str] = Header(None)) -> dict:
    check_auth(authorization, x_api_key)
    try:
        await run_add(
            req.request_id,
            [m.model_dump(exclude_none=True) for m in req.messages],
            req.user_id,
            req.session_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail={"reason": f"add failed: {exc}"}) from exc
    return {
        "success": True,
        "request_id": req.request_id,
        "user_id": req.user_id,
        "session_id": req.session_id,
    }


@app.post("/search")
async def search(req: SearchRequest, authorization: Optional[str] = Header(None), x_api_key: Optional[str] = Header(None)) -> dict:
    check_auth(authorization, x_api_key)
    try:
        data = await run_search(req.query, req.options, req.user_id, req.top_k)
    except Exception as exc:
        raise HTTPException(status_code=503, detail={"reason": f"search failed: {exc}"}) from exc
    return {"data": data}
