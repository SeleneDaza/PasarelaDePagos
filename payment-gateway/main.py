from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.db.database import Base, engine
from app.logging_config import setup_logging
from app.routers import liquidations, mock, payments, reports, ws_payments
from app.scheduler import scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Pasarela de Pagos",
    description="API REST para procesamiento de pagos con tarjeta Visa y Mastercard.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(payments.router)
app.include_router(ws_payments.router)
app.include_router(reports.router)
app.include_router(liquidations.router)

if settings.APP_ENV == "development":
    app.include_router(mock.router)


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok"}
