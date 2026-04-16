import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any

import aio_pika
import redis
import uvicorn
import yaml
from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse

MODE = os.getenv("SERVICE_MODE", "relay")
SERVICE_NAME = os.getenv("SERVICE_NAME", "service")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")


def log(message: str) -> None:
    print(f"[{SERVICE_NAME}] {message}", flush=True)


async def publish(connection: aio_pika.RobustConnection, queue_name: str, payload: dict[str, Any]) -> None:
    channel = await connection.channel()
    await channel.declare_queue(queue_name, durable=True)
    await channel.default_exchange.publish(
        aio_pika.Message(body=json.dumps(payload).encode("utf-8"), delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
        routing_key=queue_name,
    )
    await channel.close()


async def relay_loop() -> None:
    in_queue = os.getenv("IN_QUEUE")
    out_queue = os.getenv("OUT_QUEUE")

    if not in_queue or not out_queue:
        raise RuntimeError("IN_QUEUE e OUT_QUEUE são obrigatórios no modo relay")

    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await connection.channel()
    queue = await channel.declare_queue(in_queue, durable=True)
    await channel.declare_queue(out_queue, durable=True)

    log(f"Relay ativo: {in_queue} -> {out_queue}")

    async with queue.iterator() as queue_iter:
        async for message in queue_iter:
            async with message.process(requeue=False):
                payload = json.loads(message.body.decode("utf-8"))
                payload["trail"] = payload.get("trail", []) + [SERVICE_NAME]
                payload["last_updated_at"] = datetime.now(timezone.utc).isoformat()
                await publish(connection, out_queue, payload)
                log(f"Mensagem encaminhada para {out_queue}: correlation_id={payload.get('correlation_id')}")


async def publisher_once() -> None:
    out_queue = os.getenv("OUT_QUEUE", "payroll.generation.request")
    correlation_id = os.getenv("CORRELATION_ID", "e2e-correlation-001")

    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    payload = {
        "correlation_id": correlation_id,
        "employee_id": "EMP-123",
        "company_id": "COMP-456",
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "trail": [SERVICE_NAME],
    }
    await publish(connection, out_queue, payload)
    log(f"Mensagem publicada em {out_queue}: correlation_id={correlation_id}")
    await connection.close()


app = FastAPI(title="Status Generation Service")
status_events: list[str] = []


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "UP", "service": SERVICE_NAME, "mode": MODE})


@app.get("/status/{correlation_id}")
def read_status(correlation_id: str) -> JSONResponse:
    status = app.state.redis_client.get(f"status:{correlation_id}")
    if status is None:
        return JSONResponse({"found": False, "correlation_id": correlation_id}, status_code=404)
    return JSONResponse({"found": True, "correlation_id": correlation_id, "payload": json.loads(status)})


@app.get("/events")
async def events() -> StreamingResponse:
    async def event_stream():
        idx = 0
        while True:
            while idx < len(status_events):
                event_data = status_events[idx]
                idx += 1
                yield f"data: {event_data}\n\n"
            await asyncio.sleep(0.2)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


async def status_loop() -> None:
    config = {
        "redis": {
            "host": os.getenv("REDIS_HOST", "localhost"),
            "port": int(os.getenv("REDIS_PORT", "6379")),
            "password": os.getenv("REDIS_PASSWORD", ""),
            "timeout": os.getenv("REDIS_TIMEOUT", "2s"),
        }
    }
    app.state.redis_yaml = yaml.safe_dump(config)

    redis_client = redis.Redis(
        host=config["redis"]["host"],
        port=config["redis"]["port"],
        password=config["redis"]["password"] or None,
        socket_timeout=float(config["redis"]["timeout"].replace("s", "")),
        decode_responses=True,
    )
    app.state.redis_client = redis_client

    in_queue = os.getenv("IN_QUEUE", "payroll.generation.result")
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await connection.channel()
    queue = await channel.declare_queue(in_queue, durable=True)

    log(f"Status consumer ativo em {in_queue}")

    async with queue.iterator() as queue_iter:
        async for message in queue_iter:
            async with message.process(requeue=False):
                payload = json.loads(message.body.decode("utf-8"))
                correlation_id = payload.get("correlation_id", "unknown")
                payload["status"] = "PROCESSED"
                payload["status_updated_at"] = datetime.now(timezone.utc).isoformat()

                redis_client.set(f"status:{correlation_id}", json.dumps(payload))
                status_events.append(json.dumps(payload))
                log(f"Status atualizado no Redis + SSE: correlation_id={correlation_id}")


@app.on_event("startup")
async def startup_event() -> None:
    if MODE == "status":
        asyncio.create_task(status_loop())


def run_status_api() -> None:
    uvicorn.run(app, host="0.0.0.0", port=8080)


async def main() -> None:
    if MODE == "relay":
        await relay_loop()
    elif MODE == "publisher":
        await publisher_once()
    elif MODE == "status":
        run_status_api()
    else:
        raise RuntimeError(f"SERVICE_MODE inválido: {MODE}")


if __name__ == "__main__":
    asyncio.run(main())
