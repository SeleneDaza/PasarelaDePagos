# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the server
uvicorn main:app --reload

# Run with a specific port (to avoid conflicts with mock card services)
uvicorn main:app --reload --port 8002

# Install dependencies
pip install -r requirements.txt
```

There are no automated tests in this project yet.

## Architecture

This is a **FastAPI async payment gateway** that sits between a ticket-sales system and two external card-verification services (Visa and Mastercard, each a separate serverless/microservice).

**Request flow:**
1. `POST /pagos` → `PaymentService.crear_pago()` in `app/services/payment_service.py`
2. Validates `empresa_id` exists and is active (PostgreSQL via SQLAlchemy async)
3. Calls `CardClient.verificar_tarjeta()` in `app/services/card_client.py` → HTTP POST to the card service
4. Persists a `Transaccion` record with one of three outcomes:
   - `aprobado` + `no_liquidado` — card verified OK
   - `rechazado` + `None` — card service responded but card not found
   - `fallido` + `None` — network/5xx error calling the card service

**Key design decisions:**
- `numero_tarjeta` and `cvv` are **never persisted** — only the last 4 digits are stored in `cliente_id` as a temporary placeholder until the card services return a real customer ID.
- The mock router (`app/routers/mock.py`) is only mounted when `APP_ENV=development`. It simulates both card services at `/mock/visa/verificar-tarjeta` and `/mock/mastercard/verificar-tarjeta`.
- Tables are auto-created on startup via `Base.metadata.create_all`. In production, Alembic would be used instead.

## Configuration

Required `.env` variables (see `app/config.py`):
```
DATABASE_URL=postgresql+asyncpg://...
VISA_SERVICE_URL=http://...       # base URL for Visa service
MASTERCARD_SERVICE_URL=http://... # base URL for Mastercard service
APP_ENV=development               # set to "production" to disable mock routes
```

In development, `VISA_SERVICE_URL` and `MASTERCARD_SERVICE_URL` point to the same app (`localhost:8000` / `localhost:8001`) or to the mock endpoints on this server.

## Mock test cards

Visa: `4111111111111111` / cvv `123`, `4222222222222222` / cvv `456`  
Mastercard: `5111111111111118` / cvv `321`, `5222222222222220` / cvv `654`
