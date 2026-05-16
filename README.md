# Pasarela de Pagos

API REST que intermedia entre un sistema de venta de boletas y los servicios de verificación de tarjetas Visa y Mastercard. Recibe solicitudes de pago, valida la tarjeta con el proveedor correspondiente, registra el resultado en base de datos y expone reportes de transacciones pendientes de liquidación. La liquidación masiva se ejecuta automáticamente el primer día de cada mes.

---

## Requisitos

- Python 3.12+
- PostgreSQL
- Docker (para el stack de monitoreo)

---

## Ejecución del proyecto

### 1. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 2. Configurar variables de entorno

Crea un archivo `.env` en la raíz del proyecto:

```env
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/pasarela_db
VISA_SERVICE_URL=http://localhost:8000
MASTERCARD_SERVICE_URL=http://localhost:8001
APP_ENV=development
```

### 3. Iniciar la API

```bash
uvicorn main:app --reload --port 8002
```

### 4. Iniciar el stack de monitoreo (Loki + Grafana)

```bash
docker compose -f docker-compose.monitoring.yml up -d
```

---

## Servicios disponibles

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `POST` | `/pagos` | Procesa un pago con tarjeta Visa o Mastercard |
| `GET` | `/reportes/pendientes` | Lista transacciones pendientes de liquidación por empresa |
| `POST` | `/liquidaciones/batch` | Liquida masivamente transacciones pendientes |
| `GET` | `/health` | Estado de la API |
| `POST` | `/mock/visa/verificar-tarjeta` | Simulador Visa (solo en `APP_ENV=development`) |
| `POST` | `/mock/mastercard/verificar-tarjeta` | Simulador Mastercard (solo en `APP_ENV=development`) |

---

## Documentación de la API

Con la aplicación corriendo, accede a:

```
http://localhost:8002/docs
```

---

## Visualización de logs en Grafana

### 1. Agregar Loki como fuente de datos

1. Abre `http://localhost:3000`
2. Ve a **Connections → Data sources → Add new data source**
3. Selecciona **Loki**
4. En **URL** ingresa `http://loki:3100`
5. Haz clic en **Save & test**

### 2. Consultar logs

Ve a **Explore**, selecciona **Loki** y usa estas consultas:

```logql
# Todos los logs
{job="pasarela-de-pagos"}

# Solo errores y advertencias
{job="pasarela-de-pagos"} | json | level=~"WARNING|ERROR"

# Logs del servicio de pagos
{job="pasarela-de-pagos"} | json | logger="app.services.payment_service"

# Logs del servicio de reportes
{job="pasarela-de-pagos"} | json | logger="app.services.report_service"

# Logs de liquidaciones
{job="pasarela-de-pagos"} | json | logger="app.services.liquidation_service"
```
