# Ambiente E2E (Java/Spring Boot) — Status de Processamento

Você está certo em se preocupar: o ambiente agora foi ajustado para **manter arquitetura Java/Spring Boot** nos serviços.

## O que este repositório entrega

- Orquestração E2E com os componentes informados.
- RabbitMQ como backbone de eventos.
- Redis para persistência de status.
- Serviço de status consumindo `payroll.generation.result` e notificando frontend via SSE.
- Script de validação E2E sem trocar a stack dos microserviços (continua Spring Boot).

## Componentes no Compose

- `sboot-payroll-query-service`
- `boot-payroll-orchestrator-service`
- `payroll-generation-request-publisher`
- `sboot-security-base-auth-service`
- `sboot-payroll-generation-processor`
- `sboot-security-base-api-gateway`
- `sboot-payroll-calculation-service`
- `sboot-data-employe-serice`
- `sboot-data-company-serice`
- `RabbitMQ`
- `Redis`
- `sboot-payroll-events-service`
- `sboot-payroll-validation-service`
- `sboot-time-tracking-integration-service`
- `sboot-stts-base-status-generation-file`

> Observação: `sboot-security-base-api-gateway` apareceu duas vezes no seu pedido; no compose ele é definido uma vez.

## Fluxo funcional esperado

1. `payroll-generation-request-publisher` publica solicitação de geração.
2. `boot-payroll-orchestrator-service` coordena pipeline.
3. `sboot-payroll-validation-service` valida.
4. `sboot-payroll-events-service` consolida eventos.
5. `sboot-time-tracking-integration-service` integra apontamentos.
6. `sboot-payroll-calculation-service` calcula folha.
7. `sboot-payroll-generation-processor` publica em `payroll.generation.result`.
8. `sboot-stts-base-status-generation-file` consome resultado, grava no Redis e expõe SSE.

## Configuração Redis usada no status service

```yaml
redis:
  host: ${REDIS_HOST:localhost}
  port: ${REDIS_PORT:6379}
  password: ${REDIS_PASSWORD:}
  timeout: ${REDIS_TIMEOUT:2s}
```

## Pré-requisitos

- Docker + Docker Compose
- Imagens Docker dos microserviços Spring Boot já construídas/publicadas

## Subir ambiente

```bash
docker compose up -d
```

## Teste E2E

O script abaixo:
- publica uma mensagem de teste diretamente no RabbitMQ (`payroll.generation.request`),
- aguarda o status ficar disponível no endpoint do status service,
- valida resposta do status.

```bash
bash e2e/run-e2e.sh
```

## Encerrar

```bash
docker compose down -v
```
