from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db.database import engine, Base
from app.routers import payments

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Crea las tablas al iniciar (en producción se usa Alembic)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="Pasarela de Pagos",
    description="API REST para procesamiento de pagos con tarjeta Visa y Mastercard.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(payments.router)

@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok"}
