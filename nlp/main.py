import os
from dataclasses import asdict

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from pipeline.llm_client import LLMClient, resolve_ollama_url
from pipeline.pipeline import Pipeline

DB_URL = os.environ.get("DB_URL", "http://db:8001")
SQL_MODEL = os.environ.get("SQL_MODEL", "qwen2.5-coder:14b")
SYNTHESIS_MODEL = os.environ.get("SYNTHESIS_MODEL", "qwen3:32b")

app = FastAPI()

_llm_client = LLMClient(backend="ollama", model=SQL_MODEL)
_pipeline = Pipeline(
    db_url=DB_URL,
    llm_client=_llm_client,
    sql_model=SQL_MODEL,
    synthesis_model=SYNTHESIS_MODEL,
)


class QueryRequest(BaseModel):
    question: str


@app.post("/query")
def query(request: QueryRequest):
    try:
        result = _pipeline.run(request.question)
        return JSONResponse(status_code=200, content=asdict(result))
    except Exception as exc:
        return JSONResponse(status_code=200, content={"error": str(exc)})


@app.get("/health")
def health():
    return {"status": "ok", "ollama_url": resolve_ollama_url()}
