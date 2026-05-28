# 🐇 RabbitMQ Stack
 
> **Stack de mensageria assíncrona de produção**, construída com FastAPI, RabbitMQ e SQLite
 
### 🧩 O que está na stack
 
| Componente | Tecnologia | Função |
|---|---|---|
| API Produtora | `FastAPI` | Recebe pedidos HTTP e publica no broker |
| Broker | `RabbitMQ 3-management` | Garante durabilidade e roteamento das mensagens |
| Worker Consumidor | `Python + Pika` | Processa mensagens e persiste no SQLite |
| Banco de Dados | `SQLite` | Persistência leve compartilhada via volume Docker |
| Testes | `pytest + pytest-cov` | Cobertura de **98.49%** |
| Automação | `taskipy + uv` | Comandos rápidos via `pyproject.toml` |
 
### 📋 Requisitos
 
- Python **3.12**
- Docker Engine (para simulação com Compose)
- [`uv`](https://astral.sh/uv) — gerenciador de pacotes moderno

---

### 🖥️ Executando localmente
 
**1.** Sincronize o ambiente virtual:
 
```powershell
uv sync
```
 
**2.** Rode a API e o Worker em terminais separados:
 
```powershell
# Terminal 1 — API
uv run task api-dev
 
# Terminal 2 — Worker
uv run task worker-start
```
 
**3.** Teste a API:
 
```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -Method Get
```
 
### 🐳 Executando com Docker Compose (simulação integrada)
 
**1.** Construa e suba os serviços:
 
```powershell
docker compose up --build -d
```
 
**2.** Verifique os containers em execução:
 
```powershell
docker compose ps
```
 
Serviços esperados:
 
| Container | Descrição | Porta |
|---|---|---|
| `rabbitmq-broker` | Broker de mensagens | `5672` / `15672` |
| `api-produtor` | API FastAPI | `8000` |
| `worker-consumidor` | Worker assíncrono | — |
 
**3.** Envie um pedido:
 
```powershell
$body = '{"id": "1", "descricao": "Notebook ASUS", "valor": 3500.0}'
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/pedidos' -Method Post -ContentType 'application/json' -Body $body
```
 
**4.** Consulte os pedidos processados:
 
```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/pedidos' -Method Get
```

---
 
### 🏗️ Arquitetura
 
<img width="7877" height="5635" alt="Image" src="https://github.com/user-attachments/assets/0b996c01-5e4a-4045-8849-ccd281f52a9b" />

- A API publica mensagens no `pedidos_exchange` (tipo `topic`)
- Mensagens com routing key `pedidos.*` são roteadas para `pedidos_queue`
- A fila possui `x-dead-letter-exchange` apontando para `dlx_exchange`
- O Worker consome com `prefetch_count=1` e envia `basic_ack` apenas após processamento bem-sucedido

---

### 🪦 Dead Letter Exchange (DLX)
 
Mensagens que falham no processamento são automaticamente redirecionadas para `dlx_pedidos` via `dlx_exchange`, onde ficam aguardando auditoria.
 
Verifique no painel do RabbitMQ:
 
- Acesse [http://localhost:15672](http://localhost:15672) — usuário: `guest` / senha: `guest`
- Navegue em **Queues → dlx_pedidos**

### 🧪 Testes Automatizados
 
```powershell
# Rodar todos os testes
uv run task test
 
# Rodar com relatório de cobertura (mínimo 95%)
uv run task test-cov
```
 
> Cobertura atual: **98.49%** ✅

------
 
### 📋 Comandos úteis
 
| Comando | Descrição |
|---|---|
| `uv run task test` | Roda testes com `pytest` |
| `uv run task test-cov` | Roda testes com relatório de cobertura |
| `uv run task lint` | Roda o linter `ruff` |
| `uv run task rmq-status` | Imprime estado do broker via API (requer `rich`) |
| `docker compose logs -f api-produtor` | Logs da API em tempo real |
| `docker compose logs -f worker-consumidor` | Logs do Worker em tempo real |
| `docker compose logs -f rabbitmq-broker` | Logs do RabbitMQ em tempo real |
| `docker compose down` | Para todos os containers |
| `docker compose down -v` | Para containers e remove volumes |