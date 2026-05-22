# ⚙️ Passo 4/6: Worker Consumidor Pika (Conexão Local) & Resiliência AMQP

Saudações, Padawan! A API produtora está rodando e publicando pedidos. Agora, nosso desafio é implementar o **worker-consumidor** de forma robusta e resiliente usando a biblioteca `Pika`.

O Worker deve operar seguindo regras rígidas de segurança contra perda de dados:
1. **Fair Dispatch (`prefetch_count=1`)**: Não sobrecarregar um único worker, distribuindo mensagens de forma equilibrada em múltiplos consumidores em paralelo.
2. **Acks e Nacks explícitos**: Confirmar mensagens (`basic_ack`) apenas quando processadas com sucesso. Em caso de erro não tratado, rejeitá-las explicitamente (`basic_nack(requeue=False)`) para que caiam automaticamente na Dead Letter Exchange (DLX).

---

## 🧠 1. Camada de Domínio (`worker/domain/`)

O domínio do worker define a lógica de negócio do processamento assíncrono.

### 📝 Entidade de Domínio (`worker/domain/models.py`)
Utilizamos o Pydantic para modelar os dados do pedido consumido:

```python
from pydantic import BaseModel

class PedidoConsumido(BaseModel):
    id: str
    descricao: str
    valor: float
```

### 📝 Contrato do Repositório (`worker/domain/repository.py`)
Define a interface para persistir o resultado final do processamento:

```python
from abc import ABC, abstractmethod
from worker.domain.models import PedidoConsumido

class PedidoProcessadoRepository(ABC):
    @abstractmethod
    def salvar_processado(self, pedido: PedidoConsumido) -> None:
        """Persiste um pedido com status de processamento final."""
        pass
```

### 📝 Handler de Negócio (`worker/domain/handler.py`)
O caso de uso principal do Worker. Ele contém a lógica de processamento e a regra de negócio do domínio:

```python
import logging
from worker.domain.models import PedidoConsumido
from worker.domain.repository import PedidoProcessadoRepository

logger = logging.getLogger(__name__)

class ProcessarPedidoHandler:
    def __init__(self, repo: PedidoProcessadoRepository):
        self.repo = repo

    def handle(self, pedido: PedidoConsumido) -> None:
        logger.info(f"Iniciando processamento do pedido {pedido.id} — '{pedido.descricao}'")
        
        # Regra de negócio simulada: se a descrição for "item inválido",
        # simulamos uma falha grave de domínio!
        if pedido.descricao.lower() == "item inválido":
            raise ValueError("Falha de validação do domínio: este item não é elegível para processamento!")

        # Grava o sucesso do processamento no repositório de infra
        self.repo.salvar_processado(pedido)
        logger.info(f"Pedido {pedido.id} processado com sucesso!")
```

---

## 🛠️ 2. Camada de Infraestrutura (`worker/infra/`)

A infraestrutura é onde os drivers tecnológicos conectam as mensagens às regras do domínio.

### 📝 Configurações de Ambiente (`worker/infra/settings.py`)
O host padrão do broker é `localhost` (para desenvolvimento local), permitindo sobrescrita de ambiente em produção:

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

### 📝 Persistência Local de Processamento (`worker/infra/database.py`)
Grava os pedidos processados com sucesso pelo worker em um arquivo JSON específico na pasta compartilhada:

```python
import json
import os
from worker.domain.models import PedidoConsumido
from worker.domain.repository import PedidoProcessadoRepository

class PedidoProcessadoRepositoryLocal(PedidoProcessadoRepository):
    def __init__(self, filepath: str = "data/pedidos_processados.json"):
        self.filepath = filepath
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        if not os.path.exists(self.filepath):
            with open(self.filepath, "w") as f:
                json.dump([], f)

    def salvar_processado(self, pedido: PedidoConsumido) -> None:
        with open(self.filepath, "r+") as f:
            data = json.load(f)
            data.append({
                "id": pedido.id,
                "descricao": pedido.descricao,
                "valor": pedido.valor,
                "status": "PROCESSADO"
            })
            f.seek(0)
            json.dump(data, f, indent=4)
            f.truncate()
```

### 📝 Consumidor Pika Resiliente (`worker/infra/consumer.py`)
Gerencia a conexão do consumidor do RabbitMQ garantindo ACKs e NACKs seguros no protocolo AMQP:

```python
import json
import logging
import pika
from worker.domain.models import PedidoConsumido
from worker.domain.handler import ProcessarPedidoHandler

logger = logging.getLogger(__name__)

class RabbitMQConsumer:
    def __init__(self, connection_parameters: pika.ConnectionParameters, handler: ProcessarPedidoHandler):
        self.params = connection_parameters
        self.handler = handler
        self.connection = None
        self.channel = None

    def iniciar(self) -> None:
        self.connection = pika.BlockingConnection(self.params)
        self.channel = self.connection.channel()

        # 1. Configurar prefetch_count=1 (Fair Dispatch)
        # Garante que o broker não envie uma nova mensagem a este worker até que ele
        # envie o ACK correspondente da mensagem anterior.
        self.channel.basic_qos(prefetch_count=1)

        # 2. Registrar a Callback para consumo na fila
        self.channel.basic_consume(
            queue="pedidos_queue",
            on_message_callback=self._callback,
            auto_ack=False  # NUNCA use True em produção sob risco de perda de dados
        )

        logger.info("Worker inicializado com sucesso. Aguardando novos pedidos...")
        self.channel.start_consuming()

    def _callback(self, ch, method, properties, body):
        try:
            # 1. Desserialização do payload
            data = json.loads(body.decode())
            pedido = PedidoConsumido(**data)

            # 2. Executa o caso de uso no Handler de Domínio
            self.handler.handle(pedido)

            # 3. Sucesso! Envia basic_ack de confirmação definitiva
            ch.basic_ack(delivery_tag=method.delivery_tag)
            logger.info(f"ACK enviado para o pedido {pedido.id}.")
            
        except Exception as e:
            logger.error(f"Falha de processamento no Worker: {str(e)}")
            # 4. Rejeição! Envia basic_nack com requeue=False.
            # O RabbitMQ removerá a mensagem da fila principal e a encaminhará
            # automaticamente para a DLX (dlx_pedidos) para auditoria.
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            logger.warning(f"NACK enviado para a mensagem. Redirecionada para DLX.")
```

---

## ⚡ 3. Arquivo de Entrada (`worker/main.py`)

No ponto de inicialização, orquestramos a montagem unindo a Infraestrutura aos Contratos de Domínio:

```python
import logging
import pika
from worker.infra.settings import Settings
from worker.infra.database import PedidoProcessadoRepositoryLocal
from worker.domain.handler import ProcessarPedidoHandler
from worker.infra.consumer import RabbitMQConsumer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = Settings()

def main():
    repo = PedidoProcessadoRepositoryLocal()
    handler = ProcessarPedidoHandler(repo)
    
    credentials = pika.PlainCredentials(settings.RABBITMQ_USER, settings.RABBITMQ_PASS)
    parameters = pika.ConnectionParameters(
        host=settings.RABBITMQ_HOST,
        port=settings.RABBITMQ_PORT,
        credentials=credentials
    )
    
    consumer = RabbitMQConsumer(parameters, handler)
    try:
        consumer.iniciar()
    except KeyboardInterrupt:
        logger.info("Encerrando o worker graciosamente...")

if __name__ == "__main__":
    main()
```

---

## 🚀 4. Executando e validando o Fluxo de Ponta a Ponta

1. Crie o arquivo `requirements.txt` na pasta `worker/` contendo:
   ```text
   pika>=1.3.2
   pydantic>=2.6.0
   pydantic-settings>=2.2.0
   ```
2. Instale as dependências localmente.
3. Abra um terminal para rodar a API (Passo 3): `uvicorn main:app --reload` (em `api/`).
4. Abra outro terminal e inicie o Worker (em `worker/`):
   ```bash
   python main.py
   ```
5. **Cenário de Sucesso**: Envie um pedido válido via `curl` na API:
   * Verifique o log do Worker: ele deve logar o recebimento, gravar o sucesso em `worker/data/pedidos_processados.json` e emitir o **ACK** no RabbitMQ.
6. **Cenário de Falha (DLX)**: Envie um pedido com a descrição `"item inválido"`:
   * O Worker tentará processar, disparará a exceção do domínio, capturará o erro na infraestrutura, emitirá o **NACK** com `requeue=False` e a mensagem sumirá da fila principal.
   * Verifique no painel do RabbitMQ (`http://localhost:15672`) que a fila `dlx_pedidos` agora possui **1 mensagem** nela!

---

### 🧙‍♂️ Instruções do Mestre:
Escreva a infraestrutura do seu Worker, configure as callbacks para gerenciar o ciclo AMQP localmente e teste ambos os cenários (sucesso e falha).

> [!IMPORTANT]
> Quando o seu cenário de sucesso gerar o arquivo `pedidos_processados.json` e o cenário de falha enviar a mensagem para a fila do `dlx_pedidos` no broker, compartilhe os códigos e logs comigo.
> 
> Como mentor, vou analisar a sua captura de exceções e a robustez do loop. **Após validarmos o código, farei 2 a 3 perguntas reflexivas sobre o perigo do loop infinito de NACK com requeue=True e a importância de auto_ack=False** antes de avançarmos seu progresso para `66% - Passo 5/6: Testes Automatizados`.
