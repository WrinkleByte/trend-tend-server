import logging

from fastapi import FastAPI

from app.api.v1.router import api_router

# Without this, the root logger's default WARNING level silently drops our
# app.* loggers' INFO calls (e.g. core/email.py's "SMTP not configured —
# skipping send") before they reach a handler — uvicorn only configures its
# own uvicorn.*/uvicorn.access loggers, not root or ours.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="WrinkleByte API", version="0.1.0")
app.include_router(api_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
