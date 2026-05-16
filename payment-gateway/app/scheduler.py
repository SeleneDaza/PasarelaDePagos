import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.db.database import AsyncSessionLocal
from app.services.liquidation_service import LiquidationService

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")


async def _ejecutar_liquidacion_mensual() -> None:
    async with AsyncSessionLocal() as session:
        try:
            service = LiquidationService(session)
            resultado = await service.liquidar_batch()
            await session.commit()
            logger.info(
                "Liquidación mensual completada: %d transacciones liquidadas.",
                resultado.procesadas,
            )
        except Exception:
            await session.rollback()
            logger.exception("Error durante la liquidación mensual automática.")


scheduler.add_job(
    _ejecutar_liquidacion_mensual,
    CronTrigger(day=1, hour=0, minute=0),
    id="liquidacion_mensual",
    replace_existing=True,
)
