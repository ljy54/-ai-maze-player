from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from .routes.api import router
import os

app = FastAPI(title="AI迷宫玩家", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

# 读取内嵌前端页面
_HTML_PATH = os.path.join(os.path.dirname(__file__), "static", "index.html")


@app.get("/", response_class=HTMLResponse)
async def root():
    if os.path.exists(_HTML_PATH):
        with open(_HTML_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>前端页面未找到</h1>"
