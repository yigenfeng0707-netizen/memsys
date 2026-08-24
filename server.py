from typing import Any, Optional
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
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
