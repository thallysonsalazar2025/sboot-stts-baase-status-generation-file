# Ambiente E2E — Status de Processamento da Folha

Este repositório cria um ambiente de integração com os componentes solicitados para validar o fluxo fim a fim de geração de folha, com foco no microserviço de **Status de Processamento**.

## Componentes incluídos

- sboot-payroll-query-service
- boot-payroll-orchestrator-service
- payroll-generation-request-publisher
- sboot-security-base-auth-service
- sboot-payroll-generation-processor
- sboot-security-base-api-gateway
- sboot-payroll-calculation-service
- sboot-data-employe-serice
- sboot-data-company-serice
- RabbitMQ
- Redis
- sboot-payroll-events-service
- sboot-payroll-validation-service
- sboot-time-tracking-integration-service
- **sboot-stts-base-status-generation-file** (serviço especializado em status)

## Fluxo arquitetural (Orquestração vs Geração de Resultados)

### 1) Orquestração
1. `payroll-generation-request-publisher` publica em `payroll.generation.request`
2. `boot-payroll-orchestrator-service` consome e publica em `payroll.validation.request`
3. `sboot-payroll-validation-service` consome e publica em `payroll.events.request`
4. `sboot-payroll-events-service` consome e publica em `payroll.time-tracking.request`
5. `sboot-time-tracking-integration-service` consome e publica em `payroll.calculation.request`
6. `sboot-payroll-calculation-service` consome e publica em `payroll.generation.processor.request`
7. `sboot-payroll-generation-processor` consome e publica resultado em `payroll.generation.result`

### 2) Geração de resultados (Status)
8. `sboot-stts-base-status-generation-file` consome `payroll.generation.result`
9. Atualiza o Redis com status por `correlation_id`
10. Notifica front-end via **Server-Sent Events (SSE)** em `/events`

## Configuração Redis aplicada

```yaml
redis:
  host: ${REDIS_HOST:localhost}
  port: ${REDIS_PORT:6379}
  password: ${REDIS_PASSWORD:}
  timeout: ${REDIS_TIMEOUT:2s}
```

No serviço de status isso é mapeado por variáveis:
- `REDIS_HOST`
- `REDIS_PORT`
- `REDIS_PASSWORD`
- `REDIS_TIMEOUT`

## Como subir o ambiente

```bash
docker compose up --build -d
```

## Teste End-to-End

Executa o fluxo completo e valida:
- publicação inicial;
- processamento na cadeia;
- escrita no Redis;
- evento SSE emitido.

```bash
python e2e/test_e2e.py
```

## Encerramento

```bash
docker compose down -v
```
