# 📡 Passo 3/6: API Produtora FastAPI & Publisher Resiliente

Saudações, Padawan! Agora iniciamos a criação do código da nossa aplicação. Vamos desenvolver o serviço **api-produtor** aplicando os princípios de **SOLID, Clean Code e DDD em camadas**.

A API terá uma única responsabilidade: receber um pedido via HTTP, salvá-lo em nosso repositório local e enfileirá-lo na fila do RabbitMQ de forma confiável e assíncrona.

---

## 🧠 1. Definindo o Domínio (`api/domain/`)

O domínio define *o que* a nossa aplicação faz e as regras essenciais de negócio. Não há qualquer acoplamento técnico com frameworks aqui.

### 📝 Modelo de Domínio (`api/domain/models.py`)
Utilize o Pydantic para criar a entidade de negócio garantindo validação de tipos e regras logo na entrada do sistema:
```python
from pydantic import BaseModel, Field, field_validator

class Pedido(BaseModel):
    id: str = Field(..., description="Identificador único do pedido")
    descricao: str = Field(..., description="Descrição detalhada do item pedido")
    valor: float = Field(..., description="Valor monetário do pedido")

    @field_validator('valor')
    @classmethod
    def valor_deve_ser_positivo(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("valor deve ser positivo e maior que zero")
        return v
```

### 📝 Contrato do Repositório (`api/domain/repository.py`)
Crie uma classe abstrata definindo a interface (contrato) do repositório. Lembre-se: o domínio não se importa se os dados são salvos em PostgreSQL, MongoDB ou memória — ele define apenas o contrato:
```python
from abc import ABC, abstractmethod
from api.domain.models import Pedido

class PedidoRepository(ABC):
    @abstractmethod
    def salvar(self, pedido: Pedido) -> None:
        """Persiste um pedido no meio de armazenamento."""
        pass
```

---

## 🛠️ 2. Implementando a Infraestrutura (`api/infra/`)

A infraestrutura é onde os detalhes concretos e os drivers tecnológicos (como o Pika para AMQP) ganham vida.

### 📝 Banco de Dados Local (`api/infra/database.py`)
Implemente o contrato de domínio persistindo os dados localmente de forma simples (ex: salvando os pedidos em memória e gravando num arquivo JSON local):
```python
import json
import os
from api.domain.models import Pedido
from api.domain.repository import PedidoRepository

class PedidoRepositoryLocal(PedidoRepository):
    def __init__(self, filepath: str = "data/pedidos.json"):
        self.filepath = filepath
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        if not os.path.exists(self.filepath):
            with open(self.filepath, "w") as f:
                json.dump([], f)

    def salvar(self, pedido: Pedido) -> None:
        with open(self.filepath, "r+") as f:
            data = json.load(f)
            data.append(pedido.model_dump())
            f.seek(0)
            json.dump(data, f, indent=4)
            f.truncate()
```

### 📝 Declaração da Topologia AMQP (`api/infra/topology.py`)
Para manter a infraestrutura de rede robusta e evitar race conditions no RabbitMQ, crie uma classe que declare formalmente a topologia necessária para a aplicação (Exchanges, Queues, DLX e Bindings):
```python
import pika

def declarar_topologia(channel: pika.adapters.blocking_connection.BlockingChannel) -> None:
    # 1. Declarar a Dead Letter Exchange (DLX) e Fila DLX
    channel.exchange_declare(exchange="dlx_pedidos", exchange_type="fanout", durable=True)
    channel.queue_declare(queue="dlx_pedidos", durable=True)
    channel.queue_bind(exchange="dlx_pedidos", queue="dlx_pedidos")

    # 2. Declarar a Fila Principal vinculada à DLX
    arguments = {
        "x-dead-letter-exchange": "dlx_pedidos"
    }
    channel.queue_declare(queue="pedidos_queue", durable=True, arguments=arguments)

    # 3. Declarar a Exchange Principal
    channel.exchange_declare(exchange="pedidos_exchange", exchange_type="topic", durable=True)

    # 4. Vincular a Fila Principal à Exchange Principal
    channel.queue_bind(
        exchange="pedidos_exchange",
        queue="pedidos_queue",
        routing_key="pedidos.*"
    )
```

### 📝 Publisher de Mensagens Resiliente (`api/infra/publisher.py`)
Implemente um publisher de mensagens que utilize a conexão persistente e garanta a entrega usando **Publisher Confirms** do RabbitMQ:
```python
import json
import logging
import pika
from api.domain.models import Pedido

logger = logging.getLogger(__name__)

class RabbitMQPublisher:
    def __init__(self, channel: pika.adapters.blocking_connection.BlockingChannel):
        self.channel = channel
        # Habilitar Publisher Confirms para garantir entrega confiável!
        self.channel.confirm_delivery()

    def publicar_pedido(self, pedido: Pedido) -> bool:
        body = json.dumps(pedido.model_dump())
        try:
            # Publica a mensagem de forma persistente (delivery_mode=2)
            self.channel.basic_publish(
                exchange="pedidos_exchange",
                routing_key="pedidos.novo",
                body=body,
                properties=pika.BasicProperties(
                    delivery_mode=2  # Torna a mensagem persistente no disco do broker
                )
            )
            logger.info(f"Pedido {pedido.id} enviado ao broker.")
            return True
        except pika.exceptions.UnroutableError:
            logger.error("Mensagem não pôde ser roteada pelo broker.")
            return False
```

---

## ⚡ 3. Orquestrando com o FastAPI (`api/main.py`)

No ponto de entrada, implementamos o **Lifespan** para gerenciar a conexão TCP persistente com o RabbitMQ. Abrir e fechar conexões AMQP a cada requisição HTTP esgota rapidamente os recursos do servidor!

```python
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, HTTPException, Depends
import pika

from api.domain.models import Pedido
from api.infra.settings import Settings
from api.infra.database import PedidoRepositoryLocal
from api.infra.topology import declarar_topologia
from api.infra.publisher import RabbitMQPublisher

# Configuração de Logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurações do Broker
settings = Settings()

class AppState:
    connection: pika.BlockingConnection | None = None
    channel: pika.adapters.blocking_connection.BlockingChannel | None = None

state = AppState()

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup: Cria conexão única e declara topologia
    logger.info("Iniciando conexão AMQP no startup...")
    credentials = pika.PlainCredentials(settings.RABBITMQ_USER, settings.RABBITMQ_PASS)
    parameters = pika.ConnectionParameters(
        host=settings.RABBITMQ_HOST,
        port=settings.RABBITMQ_PORT,
        credentials=credentials
    )
    state.connection = pika.BlockingConnection(parameters)
    state.channel = state.connection.channel()
    
    # Declara topologia no startup de forma automatizada
    declarar_topologia(state.channel)
    
    yield  # A API FastAPI fica escutando requests HTTP dos clientes
    
    # Shutdown: Fecha conexões AMQP de forma limpa
    logger.info("Fechando conexão AMQP no shutdown...")
    if state.connection and not state.connection.is_closed:
        state.connection.close()

app = FastAPI(lifespan=lifespan)
repo = PedidoRepositoryLocal()

def get_publisher() -> RabbitMQPublisher:
    if not state.channel:
        raise HTTPException(status_code=500, detail="Broker indisponível")
    return RabbitMQPublisher(state.channel)

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/pedidos/", status_code=202)
def criar_pedido(pedido: Pedido, publisher: RabbitMQPublisher = Depends(get_publisher)):
    # 1. Salvar no repositório local (DDD Domain Model + Repository Pattern)
    repo.salvar(pedido)
    
    # 2. Publicar assincronamente no Broker AMQP
    sucesso = publisher.publicar_pedido(pedido)
    if not sucesso:
        raise HTTPException(status_code=500, detail="Erro ao publicar pedido no broker")
        
    return {"mensagem": "Pedido enfileirado", "pedido_id": pedido.id}
```

---

## 🛡️ O Selo de Qualidade do Mestre
> [!IMPORTANT]
> **Inversão de Controle e SOLID em Prática:**
> Veja que a rota `POST /pedidos/` utiliza Injeção de Dependências (`Depends(get_publisher)`) para obter o publisher concreto. O repositório concreto `repo` implementa o contrato de domínio. Isso significa que podemos facilmente substituir a persistência JSON por PostgreSQL ou MongoDB alterando apenas um adaptador de infraestrutura, sem encostar em uma única linha da nossa regra de negócio do pedido!

---

### 🧙‍♂️ Instruções do Mestre:
Escreva a base da sua API em camadas limpas, crie o lifespan e verifique a robustez do Publisher Confirms.

> [!IMPORTANT]
> Quando terminar a API, chame-me no chat. Mostre-me sua arquitetura e prepare-se: **farei perguntas sobre injeção de dependências e a resiliência do lifespan**. 
> Após passar por esta provação com sucesso, atualizarei seu progresso para `50% - Passo 4/6: Worker Consumidor`.
