import os

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates")
NLP_URL = os.environ.get("NLP_URL", "http://nlp:8002")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "result": None, "error": None, "question": ""},
    )


@app.post("/", response_class=HTMLResponse)
async def query(request: Request, question: str = Form(...)):
    result = None
    error = None
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as client:
            response = await client.post(f"{NLP_URL}/query", json={"question": question})
            data = response.json()
            if "error" in data:
                error = data["error"]
            else:
                result = data
    except Exception as exc:
        error = f"Service unavailable: {exc}"
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "question": question,
            "result": result,
            "error": error,
        },
    )
