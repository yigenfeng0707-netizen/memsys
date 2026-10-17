import hashlib
from typing import Any, Optional
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from config import AUTH_TOKEN, AUTH_TOKEN_EXTRA, AUTH_SHA256_EXTRA
from pipeline import run_add, run_search


def _sha8(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", "replace")).hexdigest()[:8]


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", "replace")).hexdigest()

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
    if not AUTH_TOKEN and not AUTH_TOKEN_EXTRA and not AUTH_SHA256_EXTRA:
        return
    supplied = ""
    source = "none"
    if x_api_key:
        supplied = x_api_key.strip()
        source = "x-api-key"
    elif authorization:
        raw = authorization.strip()
        low = raw.lower()
        for prefix in ("bearer ", "token "):
            if low.startswith(prefix):
                raw = raw[len(prefix):].strip()
                break
        supplied = raw
        source = "authorization"
    if not supplied:
        raise HTTPException(status_code=401, detail={"reason": "missing credentials", "env_sha8": _sha8(AUTH_TOKEN), "env_len": len(AUTH_TOKEN)})
    if supplied == AUTH_TOKEN:
        return
    if supplied in AUTH_TOKEN_EXTRA:
        return
    if _sha256(supplied) in AUTH_SHA256_EXTRA:
        return
    raise HTTPException(status_code=401, detail={"reason": "invalid credentials", "env_sha8": _sha8(AUTH_TOKEN), "env_len": len(AUTH_TOKEN), "supplied_sha8": _sha8(supplied), "supplied_len": len(supplied), "source": source, "supplied_head": supplied[:8]})


@app.get("/")
def root() -> dict:
    return {
        "service": "MemSys",
        "version": app.version,
        "status": "ok",
        "endpoints": {"health": "/health", "add": "/add", "search": "/search", "docs": "/docs"},
        "auth": "X-Api-Key (registered scheme); health and root are unauthenticated GET",
    }


@app.get("/health")
def health(request: Request, diag: Optional[str] = None) -> dict:
    out: dict = {"status": "ok"}
    if diag == "1":
        rows = []
        for name, value in request.headers.items():
            row = {"name": name, "len": len(value), "sha256_16": _sha256(value)[:16]}
            if name.lower() in ("authorization", "x-api-key"):
                row["sha256"] = _sha256(value)
            rows.append(row)
        out["diag"] = rows
    return out


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
async def search(req: SearchRequest, authorization: Optional[str] = Header(None), x_api_key: Optional[str] = Header(None)) -> Any:
    import json as _json
    check_auth(authorization, x_api_key)
    try:
        data = await run_search(req.query, req.options, req.user_id, req.top_k)
        safe = _json.loads(_json.dumps({"data": data}, default=str))
        return JSONResponse(content=safe)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail={"reason": f"search failed: {type(exc).__name__}"}) from exc
