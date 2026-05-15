from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db.database import Base, engine
from app.routers import payments, mock, reports
from app.config import settings


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
app.include_router(reports.router)

if settings.APP_ENV == "development":
    app.include_router(mock.router)


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok"}