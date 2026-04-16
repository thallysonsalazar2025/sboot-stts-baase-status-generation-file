#!/usr/bin/env bash
set -euo pipefail

RABBITMQ_API_URL="${RABBITMQ_API_URL:-http://localhost:15672/api}"
RABBITMQ_USER="${RABBITMQ_USER:-guest}"
RABBITMQ_PASS="${RABBITMQ_PASS:-guest}"
STATUS_BASE_URL="${STATUS_BASE_URL:-http://localhost:8080}"
CORRELATION_ID="${CORRELATION_ID:-e2e-correlation-001}"
QUEUE_NAME="${QUEUE_NAME:-payroll.generation.request}"

payload=$(cat <<JSON
{"correlation_id":"${CORRELATION_ID}","employee_id":"EMP-123","company_id":"COMP-456","source":"e2e-script"}
JSON
)

echo "[E2E] Publicando mensagem em ${QUEUE_NAME}"
curl -sS -u "${RABBITMQ_USER}:${RABBITMQ_PASS}" \
  -H 'content-type: application/json' \
  -X POST "${RABBITMQ_API_URL}/exchanges/%2F/amq.default/publish" \
  -d "{\"properties\":{},\"routing_key\":\"${QUEUE_NAME}\",\"payload\":$(jq -Rs . <<<"${payload}"),\"payload_encoding\":\"string\"}" \
  | jq .

echo "[E2E] Aguardando status em ${STATUS_BASE_URL}/status/${CORRELATION_ID}"

for i in $(seq 1 60); do
  code=$(curl -s -o /tmp/e2e-status.json -w "%{http_code}" "${STATUS_BASE_URL}/status/${CORRELATION_ID}" || true)
  if [[ "${code}" == "200" ]]; then
    echo "[E2E] Status localizado"
    cat /tmp/e2e-status.json | jq .
    exit 0
  fi
  sleep 2
done

echo "[E2E] Falha: status não disponível após timeout"
exit 1
