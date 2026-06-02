import csv
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from threading import Lock

session_id_var: ContextVar[str] = ContextVar("session_id", default="")
client_ip_var: ContextVar[str] = ContextVar("client_ip", default="")

_CSV_PATH = Path("logs/transactions.csv")
_lock = Lock()
_log_counter = 0

CSV_HEADER = [
    "timestamp", "log_id", "level", "event", "module",
    "transaction_id", "session_id", "user_id", "client_ip",
    "payment_provider", "status", "error_code", "duration_ms", "message",
]


class LogLevel(str, Enum):
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    WARN = "WARN"


class LogEvent(str, Enum):
    PAYMENT_REQUEST_SENT = "PAYMENT_REQUEST_SENT"
    PAYMENT_AUTHORIZED = "PAYMENT_AUTHORIZED"
    PAYMENT_DECLINED = "PAYMENT_DECLINED"
    PAYMENT_CAPTURED = "PAYMENT_CAPTURED"
    TICKETS_GENERATED = "TICKETS_GENERATED"
    AUTH_LOGIN_SUCCESS = "AUTH_LOGIN_SUCCESS"
    AUTH_LOGIN_FAILED = "AUTH_LOGIN_FAILED"


class LogStatus(str, Enum):
    STARTED = "STARTED"
    SENT = "SENT"
    FAILED = "FAILED"
    SUCCESS = "SUCCESS"
    CONNECTED = "CONNECTED"
    DELIVERED = "DELIVERED"
    QUEUED = "QUEUED"


def _utc_now() -> str:
    dt = datetime.now(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def _sanitize(value: str) -> str:
    return value.replace("\n", " ").replace("\r", " ")


def _write_row(
    level: LogLevel,
    event: LogEvent,
    module: str,
    message: str,
    *,
    transaction_id: str = "",
    session_id: str = "",
    user_id: str = "",
    client_ip: str = "",
    payment_provider: str = "",
    status: str = "",
    error_code: str = "",
    duration_ms: int | str = "",
) -> None:
    global _log_counter
    ts = _utc_now()
    with _lock:
        _log_counter += 1
        log_id = _log_counter
        row = [
            ts,
            str(log_id),
            level.value,
            event.value,
            module,
            transaction_id,
            session_id or session_id_var.get(),
            user_id,
            client_ip or client_ip_var.get(),
            payment_provider,
            status,
            error_code,
            str(duration_ms) if duration_ms != "" else "",
            _sanitize(message),
        ]
        needs_header = not _CSV_PATH.exists() or _CSV_PATH.stat().st_size == 0
        with _CSV_PATH.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            if needs_header:
                writer.writerow(CSV_HEADER)
            writer.writerow(row)


def logInfo(event: LogEvent, module: str, message: str, **kwargs) -> None:
    _write_row(LogLevel.INFO, event, module, message, **kwargs)


def logSuccess(event: LogEvent, module: str, message: str, **kwargs) -> None:
    _write_row(LogLevel.SUCCESS, event, module, message, **kwargs)


def logWarn(event: LogEvent, module: str, message: str, **kwargs) -> None:
    _write_row(LogLevel.WARN, event, module, message, **kwargs)


def logError(
    event: LogEvent,
    module: str,
    message: str,
    *,
    error_code: str = "",
    technical_detail: str = "",
    functional_detail: str = "",
    exception: BaseException | None = None,
    **kwargs,
) -> None:
    if technical_detail or functional_detail or exception:
        parts = []
        if technical_detail:
            parts.append(f"technical={technical_detail}")
        if functional_detail:
            parts.append(f"functional={functional_detail}")
        if exception:
            parts.append(f"with exception: {str(exception)}")
            parts.append(f"throwable={type(exception).__name__}: {str(exception)}")
        msg = " | ".join(parts)
    else:
        msg = message
    _write_row(
        LogLevel.ERROR, event, module,
        msg,
        error_code=error_code,
        **kwargs,
    )


def elapsed_ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


def init_csv_log() -> None:
    global _log_counter
    _CSV_PATH.parent.mkdir(exist_ok=True)
    if _CSV_PATH.exists() and _CSV_PATH.stat().st_size > 0:
        with _CSV_PATH.open("r", encoding="utf-8") as f:
            data_rows = sum(1 for line in f if line.strip()) - 1
            _log_counter = max(0, data_rows)
