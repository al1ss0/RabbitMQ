# 📡 Passo 3/6: API Produtora FastAPI & Publisher Resiliente (Conexão Local)

Saudações, Padawan! Agora iniciaremos o desenvolvimento do código da nossa aplicação. Vamos implementar o serviço **api-produtor** aplicando os princípios de **SOLID, Clean Code e DDD Estratégico em camadas**.

Neste passo, você irá programar a API localmente na sua máquina e conectá-la ao container do RabbitMQ Broker que subimos no Passo 2. Isso facilita a depuração imediata e garante um ciclo de feedback rápido antes de empacotarmos tudo em containers de produção.

---

## 🧠 1. Camada de Domínio (`api/domain/`)

O Domínio define *o que* a nossa aplicação faz e suas regras essenciais de negócio. Não há qualquer acoplamento técnico com frameworks aqui.

### 📝 Entidade de Negócio (`api/domain/models.py`)
Utilize o Pydantic para criar a entidade `Pedido`, garantindo validação de tipos e validações de regras de negócio logo na entrada do sistema:

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
            raise ValueError("O valor do pedido deve ser maior que zero")
        return v
```

### 📝 Contrato do Repositório (`api/domain/repository.py`)
Crie o contrato (interface) abstrato do repositório de persistência. O domínio não sabe e não se importa se os dados serão salvos em memória, arquivo JSON ou PostgreSQL:

```python
from abc import ABC, abstractmethod
from api.domain.models import Pedido

class PedidoRepository(ABC):
    @abstractmethod
    def salvar(self, pedido: Pedido) -> None:
        """Persiste um pedido no meio de armazenamento físico."""
        pass
```

---

## 🛠️ 2. Camada de Infraestrutura (`api/infra/`)

A infraestrutura é onde os adaptadores de tecnologia concreta (como a conexão de banco físico e a biblioteca Pika para o RabbitMQ) ganham vida.

### 📝 Configurações de Ambiente (`api/infra/settings.py`)
Usamos o `pydantic-settings` para gerenciar variáveis de ambiente de forma segura. O host padrão é `localhost` (para rodar localmente), mas poderá ser facilmente sobrescrito no ambiente Docker:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    RABBITMQ_HOST: str = "localhost"  # Default para desenvolvimento local
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "guest"
    RABBITMQ_PASS: str = "guest"

    class Config:
        env_file = ".env"
```

> [!NOTE]
> Lembre-se de adicionar `pydantic-settings` no seu `requirements.txt`.

### 📝 Persistência Local em JSON (`api/infra/database.py`)
Implementamos o contrato do repositório gravando os dados fisicamente em um arquivo JSON local na pasta `data/` compartilhada:

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
Criamos um inicializador de rede responsável por declarar de forma resiliente as Exchanges, as Filas, a Dead Letter Exchange (DLX) de falhas e as regras de roteamento (bindings) no Broker:

```python
import pika

def declarar_topologia(channel: pika.adapters.blocking_connection.BlockingChannel) -> None:
    # 1. Declarar a Dead Letter Exchange (DLX) e Fila DLX para mensagens com erro
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

    # 4. Vincular a Fila Principal à Exchange Principal (pedidos.*)
    channel.queue_bind(
        exchange="pedidos_exchange",
        queue="pedidos_queue",
        routing_key="pedidos.*"
    )
```

### 📝 Publisher de Mensagens Resiliente (`api/infra/publisher.py`)
Implemente o Publisher que realiza a serialização e publica a mensagem de forma durável usando **Publisher Confirms** do RabbitMQ para garantir entrega segura ao Broker:

```python
import json
import logging
import pika
from api.domain.models import Pedido

logger = logging.getLogger(__name__)

class RabbitMQPublisher:
    def __init__(self, channel: pika.adapters.blocking_connection.BlockingChannel):
        self.channel = channel
        # Habilita o Publisher Confirms na conexão
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
                    delivery_mode=2  # Persiste a mensagem no disco do broker
                )
            )
            logger.info(f"Pedido {pedido.id} publicado com sucesso.")
            return True
        except pika.exceptions.UnroutableError:
            logger.error(f"Mensagem do pedido {pedido.id} não pôde ser roteada pelo broker.")
            return False
```

---

## ⚡ 3. Orquestração e Ponto de Entrada (`api/main.py`)

No ponto de entrada, implementamos o **Lifespan** do FastAPI para gerenciar a conexão TCP persistente com o RabbitMQ. Abrir e fechar conexões AMQP a cada requisição HTTP esgota rapidamente os recursos TCP!

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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = Settings()

class AppState:
    connection: pika.BlockingConnection | None = None
    channel: pika.adapters.blocking_connection.BlockingChannel | None = None

state = AppState()

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # STARTUP: Estabelece conexão única persistente
    logger.info("Estabelecendo conexão TCP persistente com RabbitMQ...")
    credentials = pika.PlainCredentials(settings.RABBITMQ_USER, settings.RABBITMQ_PASS)
    parameters = pika.ConnectionParameters(
        host=settings.RABBITMQ_HOST,
        port=settings.RABBITMQ_PORT,
        credentials=credentials
    )
    state.connection = pika.BlockingConnection(parameters)
    state.channel = state.connection.channel()
    
    # Declara toda a topologia AMQP de forma automatizada
    declarar_topologia(state.channel)
    
    yield  # A API fica online servindo requisições HTTP
    
    # SHUTDOWN: Fecha conexões de forma limpa e segura
    logger.info("Fechando conexões AMQP de forma segura...")
    if state.connection and not state.connection.is_closed:
        state.connection.close()

app = FastAPI(lifespan=lifespan)
repo = PedidoRepositoryLocal()

def get_publisher() -> RabbitMQPublisher:
    if not state.channel:
        raise HTTPException(status_code=500, detail="Broker AMQP indisponível")
    return RabbitMQPublisher(state.channel)

@app.post("/pedidos/", status_code=202)
def criar_pedido(pedido: Pedido, publisher: RabbitMQPublisher = Depends(get_publisher)):
    # 1. Persistência de auditoria física no repositório de infraestrutura local
    repo.salvar(pedido)
    
    # 2. Enfileiramento assíncrono e persistente no Broker
    sucesso = publisher.publicar_pedido(pedido)
    if not sucesso:
        raise HTTPException(status_code=500, detail="Falha crítica ao publicar mensagem no broker")
        
    return {"status": "Pedido Aceito e Enfileirado", "pedido_id": pedido.id}
```

---

## 🚀 4. Executando e Testando Localmente

1. Crie o arquivo `requirements.txt` na pasta `api/` contendo:
   ```text
   fastapi>=0.110.0
   uvicorn>=0.28.0
   pika>=1.3.2
   pydantic>=2.6.0
   pydantic-settings>=2.2.0
   ```
2. Instale as dependências localmente na sua máquina.
3. Certifique-se de que o container do RabbitMQ (Passo 2) está rodando.
4. Execute a API a partir do diretório `api/`:
   ```bash
   uvicorn main:app --reload
   ```
5. Faça uma requisição POST de teste usando curl ou a ferramenta swagger da API (`http://localhost:8000/docs`):
   ```bash
   curl -X POST "http://localhost:8000/pedidos/" \
        -H "Content-Type: application/json" \
        -d '{"id": "ped-001", "descricao": "Espada de Treino Jedi", "valor": 150.00}'
   ```
6. Acesse o Painel de Gerenciamento do RabbitMQ (`http://localhost:15672`) e verifique que a fila `pedidos_queue` foi criada automaticamente e que existe **1 mensagem** nela aguardando consumo!

---

### 🧙‍♂️ Instruções do Mestre:
Escreva os códigos da sua API organizados em suas devidas pastas de Domínio e Infraestrutura conforme especificado. 

> [!IMPORTANT]
> Quando o seu endpoint `POST /pedidos/` estiver respondendo HTTP 202 com sucesso e você visualizar a mensagem enfileirada no painel do RabbitMQ, compartilhe o código dos seus arquivos comigo no chat.
> 
> Como seu mentor, vou ativamente lhe ajudar a depurar o ciclo de conexão local e propor melhorias de Clean Code e SOLID na separação em camadas. **Após validarmos o código, farei 2 a 3 perguntas reflexivas baseadas na injeção de dependência do FastAPI e no papel do Lifespan** antes de avançarmos o seu progresso para `50% - Passo 4/6: Worker Consumidor Pika`.
