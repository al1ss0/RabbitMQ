# 🚀 Passo 6/6: Conteinerização Integrada, Simulação Sob Carga & Documentação Premium

Parabéns pela resiliência, Padawan! Você chegou ao último passo da nossa jornada. Suas aplicações (API e Worker) estão totalmente codificadas e validadas localmente com uma suite rica de testes automatizados.

Agora, nosso objetivo é envelopar toda a nossa aplicação em containers de produção usando **Dockerfiles** otimizados e atualizar o **Docker Compose** para orquestrar a stack completa integrada em uma rede privada isolada de produção. Para finalizar, simularemos o comportamento em lote sob carga de concorrência, verificaremos a resiliência e documentaremos o seu projeto de forma premium.

---

## 🐳 1. Criando os Dockerfiles de Produção

Cada aplicação Python (`api` e `worker`) deve conter o seu próprio `Dockerfile` otimizado. Usaremos imagens baseadas em `python:3.12-slim` para garantir leveza, segurança e velocidade.

### 📝 Dockerfile da API (`api/Dockerfile`)
Crie o arquivo [api/Dockerfile](file:///api/Dockerfile) com a especificação de produção:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Evita que o Python grave arquivos .pyc no disco e ativa o buffer de logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 📝 Dockerfile do Worker (`worker/Dockerfile`)
Crie o arquivo [worker/Dockerfile](file:///worker/Dockerfile) de produção:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

---

## 🏗️ 2. O Docker Compose Integrado e Resiliente

Com os Dockerfiles criados, vamos atualizar o nosso arquivo `docker-compose.yml` localizado na raiz do projeto. Ele passará a gerenciar os 3 serviços integrados em uma rede virtual bridge.

Substituiremos a variável de conexão `RABBITMQ_HOST` para `rabbitmq-broker` para que a API e o Worker conversem usando a rede interna do Docker. Também utilizaremos a diretiva de **Healthcheck** para garantir que a API e o Worker iniciem apenas quando o Broker do RabbitMQ estiver de fato pronto para receber conexões AMQP.

Atualize o arquivo [docker-compose.yml](file:///docker-compose.yml) com a orquestração integrada:

```yaml
version: '3.8'

services:
  rabbitmq-broker:
    image: rabbitmq:3.12-management-alpine
    container_name: rabbitmq-broker
    ports:
      - "5672:5672"     # Porta AMQP
      - "15672:15672"   # Porta do Painel Administrativo Web
    environment:
      RABBITMQ_DEFAULT_USER: guest
      RABBITMQ_DEFAULT_PASS: guest
    healthcheck:
      test: ["CMD-SHELL", "rabbitmq-diagnostics -q check_running"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - rabbitmq-network

  api-produtor:
    build:
      context: ./api
      dockerfile: Dockerfile
    container_name: api-produtor
    ports:
      - "8000:8000"
    environment:
      - RABBITMQ_HOST=rabbitmq-broker
      - RABBITMQ_PORT=5672
      - RABBITMQ_USER=guest
      - RABBITMQ_PASS=guest
    depends_on:
      rabbitmq-broker:
        condition: service_healthy  # Garante startup seguro pós-inicialização do Broker!
    volumes:
      - ./data:/app/data            # Volume compartilhado para persistência física
    networks:
      - rabbitmq-network

  worker-consumidor:
    build:
      context: ./worker
      dockerfile: Dockerfile
    container_name: worker-consumidor
    environment:
      - RABBITMQ_HOST=rabbitmq-broker
      - RABBITMQ_PORT=5672
      - RABBITMQ_USER=guest
      - RABBITMQ_PASS=guest
    depends_on:
      rabbitmq-broker:
        condition: service_healthy  # Garante startup seguro pós-inicialização do Broker!
    volumes:
      - ./data:/app/data            # Volume compartilhado para persistência física
    networks:
      - rabbitmq-network

networks:
  rabbitmq-network:
    driver: bridge
```

### 🚀 Subindo a Stack Completa
Execute o comando na raiz para compilar os Dockerfiles e subir o ecossistema integrado:
```bash
docker compose up --build -d
```

---

## 📡 3. Testando via REST Client (`requests.http`)

Para simularmos carga concorrente de produção, crie um arquivo chamado `requests.http` na raiz do projeto. Ele permite rodar requisições HTTP em lote e monitorar as métricas da API administrativa do RabbitMQ:

```http
### Variáveis globais
@api = http://localhost:8000
@rmq = http://localhost:15672/api
@rmq_auth = Basic guest guest

# =============================================================================
# 1. Requisições na API Produtora FastAPI Conteinerizada
# =============================================================================

### 🟢 Health check da API
GET {{api}}/health

###

### 🔵 Enviar Pedido Válido (HTTP 202 - Enfileirado)
POST {{api}}/pedidos/
Content-Type: application/json

{
  "id": "ped-prod-100",
  "descricao": "Sabre de Luz Vermelho",
  "valor": 1900.00
}

###

### 🔴 Enviar Pedido Inválido (HTTP 422 - Rejeitado no Pydantic)
POST {{api}}/pedidos/
Content-Type: application/json

{
  "id": "ped-prod-101",
  "descricao": "Filtro de Ar Estelar",
  "valor": -5.00
}

###

### 🟡 Enviar Pedido com Erro de Domínio (HTTP 202 aceito na API -> Enviado para DLX no Worker)
POST {{api}}/pedidos/
Content-Type: application/json

{
  "id": "ped-prod-102",
  "descricao": "item inválido",
  "valor": 120.00
}

###

### 🚀 Simular Lote para Testar Fair Dispatch (Concorrência)
POST {{api}}/pedidos/
Content-Type: application/json

{ "id": "ped-lote-1", "descricao": "Cristal Kyber Verde", "valor": 300.0 }
###
POST {{api}}/pedidos/
Content-Type: application/json

{ "id": "ped-lote-2", "descricao": "Cristal Kyber Azul", "valor": 300.0 }
###
POST {{api}}/pedidos/
Content-Type: application/json

{ "id": "ped-lote-3", "descricao": "Cristal Kyber Roxo", "valor": 350.0 }


# =============================================================================
# 2. Consultando a API Administrativa do RabbitMQ
# =============================================================================

### 📊 Visão Geral de Filas
GET {{rmq}}/queues
Authorization: {{rmq_auth}}

###

### 📈 Métricas da Fila Principal (pedidos_queue)
GET {{rmq}}/queues/%2F/pedidos_queue
Authorization: {{rmq_auth}}

###

### 📉 Métricas da Fila de Erros (dlx_pedidos)
GET {{rmq}}/queues/%2F/dlx_pedidos
Authorization: {{rmq_auth}}
```

---

## 📝 4. Documentação Premium (`README.md`)

Crie o arquivo [README.md](file:///README.md) definitivo do seu projeto na raiz, contendo:
1. **Visão Geral e Arquitetura**: O diagrama de sequência e o mapeamento de diretórios do DDD.
2. **Instruções de Inicialização**: O comando `docker compose up --build -d`.
3. **Simulação Prática**: Como testar usando o `requests.http`.
4. **Comportamento de Escalar Consumidores**: Como rodar o comando para escalar o processamento paralelo em 3 workers, assistindo a distribuição equilibrada via Fair Dispatch:
   ```bash
   docker compose up --scale worker-consumidor=3 -d
   ```
5. **Logs em Tempo Real**: `docker logs -f worker-consumidor` para visualizar os logs de ACKs e NACKs ocorrendo.

---

### 🧙‍♂️ Instruções do Mestre:
Crie os Dockerfiles, configure o Docker Compose integrado completo, execute a simulação sob carga e elabore a documentação final.

> [!IMPORTANT]
> Quando toda a stack estiver de pé via containers do Compose e você demonstrar a escalabilidade com o scale e o README impecável, me chame no chat compartilhando suas configurações finais e evidências dos testes.
> 
> Como mentor, vou lhe ajudar a depurar o build de rede e o startup seguro. **Após validarmos o projeto final, apresentarei a você o Quiz de Fixação Final Interativo com 4 perguntas estratégicas** para certificar sua conquista da maestria no design de mensageria assíncrona! Que a Força esteja com você na reta final!
