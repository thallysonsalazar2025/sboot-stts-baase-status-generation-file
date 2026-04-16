import asyncio
import json
from datetime import datetime, timezone

import aio_pika
import httpx

RABBITMQ_URL = "amqp://guest:guest@localhost:5672/"
STATUS_URL = "http://localhost:8080"
CORRELATION_ID = "e2e-correlation-001"


async def publish_initial_message() -> None:
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await connection.channel()
    queue_name = "payroll.generation.request"
    await channel.declare_queue(queue_name, durable=True)
    payload = {
        "correlation_id": CORRELATION_ID,
        "employee_id": "EMP-123",
        "company_id": "COMP-456",
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "trail": ["e2e-test"],
    }
    await channel.default_exchange.publish(
        aio_pika.Message(body=json.dumps(payload).encode("utf-8")),
        routing_key=queue_name,
    )
    await connection.close()


async def wait_status_ready(client: httpx.AsyncClient) -> None:
    for _ in range(60):
        try:
            r = await client.get(f"{STATUS_URL}/health", timeout=2)
            if r.status_code == 200:
                return
        except Exception:
            pass
        await asyncio.sleep(1)
    raise RuntimeError("Serviço de status não respondeu /health")


async def wait_final_status(client: httpx.AsyncClient) -> dict:
    for _ in range(60):
        r = await client.get(f"{STATUS_URL}/status/{CORRELATION_ID}", timeout=2)
        if r.status_code == 200:
            body = r.json()
            payload = body.get("payload", {})
            if payload.get("status") == "PROCESSED":
                return payload
        await asyncio.sleep(1)
    raise RuntimeError("Status final não encontrado no Redis")


async def main() -> None:
    async with httpx.AsyncClient() as client:
        await wait_status_ready(client)
        await publish_initial_message()
        payload = await wait_final_status(client)

    trail = payload.get("trail", [])
    required = {
        "boot-payroll-orchestrator-service",
        "sboot-payroll-validation-service",
        "sboot-payroll-events-service",
        "sboot-time-tracking-integration-service",
        "sboot-payroll-calculation-service",
        "sboot-payroll-generation-processor",
    }

    missing = sorted([name for name in required if name not in trail])
    if missing:
        raise RuntimeError(f"Fluxo incompleto, faltaram serviços no trail: {missing}")

    print("E2E OK: status processado e fluxo completo validado")


if __name__ == "__main__":
    asyncio.run(main())
