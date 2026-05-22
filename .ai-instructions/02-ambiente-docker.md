# 🐳 Passo 2/6: Ambiente de Orquestração com Docker Compose e RabbitMQ

Saudações, Padawan! Agora que você dominou a arquitetura em camadas e o fluxo da nossa stack de mensageria, o próximo passo é criar o ambiente de execução e orquestração usando **Docker** e **Docker Compose**.

Nossa stack é composta por três serviços principais que precisam rodar de forma isolada, mas perfeitamente comunicáveis em rede:
1. **rabbitmq-broker**: O intermediário de mensagens (RabbitMQ com plugin de gerenciamento habilitado).
2. **api-produtor**: A aplicação web (FastAPI) que produz e enfileira pedidos na fila.
3. **worker-consumidor**: O worker Python (Pika consumer) que consome e processa pedidos.

---

## 🏗️ Configurando a Topologia com Docker Compose

Você deve criar na raiz do seu projeto um arquivo `docker-compose.yml` altamente resiliente. É crucial configurar um **Healthcheck** para o RabbitMQ, garantindo que a API e o Worker iniciem apenas após o Broker estar 100% pronto para aceitar conexões TCP.

Aqui está o blueprint arquitetural do seu `docker-compose.yml`:

```yaml
version: '3.8'

services:
  rabbitmq-broker:
    image: rabbitmq:3.12-management-alpine
    container_name: rabbitmq-broker
    ports:
      - "5672:5672"     # Porta AMQP do Broker
      - "15672:15672"   # Porta do painel de administração web (Management Console)
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
        condition: service_healthy
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
        condition: service_healthy
    networks:
      - rabbitmq-network

networks:
  rabbitmq-network:
    driver: bridge
```

---

## 📦 Construindo as Imagens Docker (Dockerfiles)

Cada serviço Python (`api` e `worker`) deve conter o seu respectivo `Dockerfile` otimizado para produção. Use imagens Python baseadas em Alpine ou Slim para otimizar o tamanho e velocidade da stack.

### 📝 Dockerfile da API (`api/Dockerfile`)
```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Instalação de dependências via uv ou pip
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 📝 Dockerfile do Worker (`worker/Dockerfile`)
```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

---

## 🛡️ O Segredo da Resiliência do Mestre
> [!CAUTION]
> **O erro clássico do startup precipitado:**
> Dizer apenas `depends_on: [rabbitmq-broker]` faz com que o Docker Compose inicie a API e o Worker assim que o container do RabbitMQ é criado. No entanto, o motor do RabbitMQ leva cerca de 20 a 30 segundos para inicializar sua JVM e portas de escuta internas.
> 
> A diretiva `condition: service_healthy` combinada com o comando `rabbitmq-diagnostics` no healthcheck impede falhas prematuras de conexão TCP recusada (`ConnectionRefusedError`) nas nossas aplicações, mantendo a stack limpa e estável.

---

### 🧙‍♂️ Instruções do Mestre:
Implemente os arquivos de orquestração Docker conforme a especificação e verifique se a topologia de rede está correta. 

> [!IMPORTANT]
> Quando finalizar, sinalize para mim (o **Jedi da Mensageria**) no chat informando os detalhes da sua implementação. 
> Prepare-se para responder a perguntas reflexivas sobre o comportamento do docker compose e o startup seguro. 
> Após responder satisfatoriamente, atualizarei seu progresso para `33% - Passo 3/6: API Produtora FastAPI`.
