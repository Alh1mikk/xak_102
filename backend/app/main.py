from app.routers import events, sources, ai
app.include_router(events.router)
app.include_router(sources.router)
app.include_router(ai.router)  # пока можно заглушку