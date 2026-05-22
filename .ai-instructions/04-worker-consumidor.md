# ⚙️ Passo 4/6: Worker Consumidor Resiliente & Tolerância a Falhas

Saudações, Padawan! A API produtora está completa e enviando mensagens de forma persistente. Agora, nosso desafio é implementar o **worker-consumidor** de forma robusta e resiliente.

O Worker deve operar seguindo regras rígidas de segurança contra perda de dados:
1. **Fair Dispatch (`prefetch_count=1`)**: Não sobrecarregar um único worker, distribuindo as mensagens de forma equilibrada em múltiplos consumidores paralelos.
2. **Acks e Nacks explícitos**: Confirmar mensagens apenas quando processadas com sucesso. Em caso de erro não tratado, rejeitá-las explicitamente para que caiam automaticamente na DLX.

---

## 🧠 1. Domínio do Worker (`worker/domain/`)

O domínio do worker foca em *como processar* a mensagem que chega e nos contratos de negócio correspondentes.

### 📝 Modelo do Pedido no Consumidor (`worker/domain/models.py`)
```python
from pydantic import BaseModel

class PedidoConsumido(BaseModel):
    id: str
    descricao: str
    valor: float
```

### 📝 Contrato do Repositório (`worker/domain/repository.py`)
Define o contrato do worker para gravar o resultado do processamento final do pedido:
```python
from abc import ABC, abstractmethod
from worker.domain.models import PedidoConsumido

class PedidoProcessadoRepository(ABC):
    @abstractmethod
    def salvar_processado(self, pedido: PedidoConsumido) -> None:
        """Persiste um pedido com status de processamento final."""
        pass
```

### 📝 Caso de Uso/Handler de Domínio (`worker/domain/handler.py`)
A regra de negócio e fluxo lógico do que acontece no recebimento de um pedido:
```python
import logging
from worker.domain.models import PedidoConsumido
from worker.domain.repository import PedidoProcessadoRepository

logger = logging.getLogger(__name__)

class ProcessarPedidoHandler:
    def __init__(self, repo: PedidoProcessadoRepository):
        self.repo = repo

    def handle(self, pedido: PedidoConsumido) -> None:
        logger.info(f"Iniciando processamento do pedido {pedido.id} — {pedido.descricao}")
        
        # Simulação de regra de negócio do domínio:
        # Ex: se o pedido for um "Item inválido", simular uma falha grave de negócio para fins educacionais!
        if pedido.descricao.lower() == "item inválido":
            raise ValueError("Falha de validação do domínio: este item não pode ser processado!")

        # Persistir o sucesso
        self.repo.salvar_processado(pedido)
        logger.info(f"Pedido {pedido.id} processado com sucesso.")
```

---

## 🛠️ 2. Infraestrutura do Worker (`worker/infra/`)

A infraestrutura conecta os eventos vindos do RabbitMQ às regras de negócio definidas no Domínio.

### 📝 Repositório Concreto de Persistência (`worker/infra/database.py`)
Salva em um arquivo JSON local os pedidos que foram processados pelo worker:
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
Implemente o loop de escuta do RabbitMQ que manipula ACKs e NACKs com excelência:
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
        # termine e envie o ACK da mensagem atual.
        self.channel.basic_qos(prefetch_count=1)

        # 2. Registrar a Callback para processamento na fila
        self.channel.basic_consume(
            queue="pedidos_queue",
            on_message_callback=self._callback,
            auto_ack=False  # NUNCA use True para evitar perda de dados sob falhas!
        )

        logger.info("Worker inicializado. Aguardando mensagens...")
        self.channel.start_consuming()

    def _callback(self, ch, method, properties, body):
        try:
            # 1. Deserializar a mensagem
            data = json.loads(body.decode())
            pedido = PedidoConsumido(**data)

            # 2. Chamar o Handler de Domínio
            self.handler.handle(pedido)

            # 3. Sucesso! Enviar basic_ack de confirmação de processamento seguro
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
        except Exception as e:
            logger.error(f"Erro grave no processamento. Rejeitando mensagem: {str(e)}")
            # 4. Falha! Enviar basic_nack com requeue=False.
            # O RabbitMQ encaminhará a mensagem automaticamente para a DLX (dlx_pedidos)
            # impedindo que ela fique presa num loop infinito na fila principal!
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
```

---

## ⚡ 3. Arquivo de Entrada (`worker/main.py`)

No arquivo de execução principal, orquestramos a inicialização conectando a Infraestrutura aos Contratos de Domínio:

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
    # 1. Instanciar Adaptadores de Infra
    repo = PedidoProcessadoRepositoryLocal()
    
    # 2. Instanciar Handlers de Domínio (Injeção de Dependência)
    handler = ProcessarPedidoHandler(repo)
    
    # 3. Configurar Parâmetros do Broker
    credentials = pika.PlainCredentials(settings.RABBITMQ_USER, settings.RABBITMQ_PASS)
    parameters = pika.ConnectionParameters(
        host=settings.RABBITMQ_HOST,
        port=settings.RABBITMQ_PORT,
        credentials=credentials
    )
    
    # 4. Iniciar Consumo
    consumer = RabbitMQConsumer(parameters, handler)
    try:
        consumer.iniciar()
    except KeyboardInterrupt:
        logger.info("Encerrando o worker de forma limpa...")

if __name__ == "__main__":
    main()
```

---

## 🛡️ O Selo de Qualidade do Mestre
> [!WARNING]
> **O Perigo do `auto_ack=True` e `requeue=True` no Lado Sombrio:**
> 1. Setar `auto_ack=True` faz o broker remover a mensagem da fila assim que a envia pela rede. Se o worker cair durante o processamento de banco ou CPU, a mensagem é **perdida para sempre**!
> 2. Enviar um `basic_nack` com `requeue=True` em caso de erro de lógica de dados/validação (como o "Item inválido") faz a mensagem ser devolvida à fila no mesmo instante, reiniciando o loop de erro. Isso cria um loop infinito de consumo de CPU/Logs!
> 
> Usar `auto_ack=False` e `requeue=False` em cenários de erro de negócio direciona a mensagem para a DLX, mantendo a stack saudável e auditável.

---

### 🧙‍♂️ Instruções do Mestre:
Escreva a infraestrutura do seu Worker consumidor, configure as callbacks para enviar ACKs e NACKs com precisão cirúrgica e verifique o Fair Dispatch.

> [!IMPORTANT]
> Quando concluir a implementação do seu Worker, sinalize para mim no chat. 
> Prepare-se para ser interrogado sobre: **a diferença prática entre ACKs/NACKs e o comportamento da DLX sob falhas**.
> Após provar sua maestria, atualizarei seu progresso para `66% - Passo 5/6: Testes Automatizados`.
