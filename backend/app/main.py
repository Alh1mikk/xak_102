# backend/app/main.py
from fastapi import FastAPI
from app.routers import events, sources, ai

app = FastAPI(
    title="Афиша культуры Башкортостана",
    version="0.1.0",
)

app.include_router(events.router)
app.include_router(sources.router)
app.include_router(ai.router)


@app.get("/")
async def root():
    return {"status": "ok", "service": "afisha-rb"}