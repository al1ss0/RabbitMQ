# 🧪 Passo 5/6: Testes Automatizados, Mocks e Validação de Qualidade

Saudações, Padawan! A API e o seu Worker em rede local conversando e persistindo dados já estão! Orgulhoso do seu progresso na força eu estou, sim! No entanto, na Engenharia de Software profissional de elite, código sem **Testes Automatizados** considerado pronto nunca é!

Graças à nossa arquitetura em camadas do **DDD**, testar a lógica do domínio extremamente simples e rápido será, pois ela acoplamento físico com o RabbitMQ ou bancos concretos não possui! E para testarmos a infraestrutura e as rotas da nossa API sem dependermos do Broker ligado em rede, fixtures de **Mocking** profissional nós criaremos!

---

## 🏗️ 1. Estruturando a Pasta de Testes

No ecossistema unificado sincronizado com o `uv`, criaremos a nossa suite estruturando a pasta de testes de forma idêntica à referência, mas mantendo todas as fixtures mockadas de forma centralizada e limpa na raiz de `tests/conftest.py`:

```
rabbitmq-stack/
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Todas as fixtures globais unificadas (Mocks de Pika, FastAPI e SQLite)
│   ├── api/
│   │   ├── __init__.py
│   │   ├── domain/
│   │   │   ├── __init__.py
│   │   │   ├── test_models.py       # Testes unitários do modelo Pydantic
│   │   │   └── test_repository.py   # Testes de integração do repositório da API
│   │   ├── infra/
│   │   │   ├── __init__.py
│   │   │   ├── test_database.py     # Testes das transações do SQLite
│   │   │   ├── test_publisher.py    # Testes do publicador AMQP da API
│   │   │   ├── test_settings.py     # Testes da configuração da API
│   │   │   └── test_topology.py     # Testes da topologia AMQP da API
│   │   └── test_main.py             # Testes de rotas e integração HTTP mockada
│   └── worker/
│       ├── __init__.py
│       ├── domain/
│       │   ├── __init__.py
│       │   ├── test_models.py       # Testes unitários do Dataclass do Worker
│       │   ├── test_handler.py      # Testes do processador de casos de uso (Handler)
│       │   └── test_repository.py   # Testes do repositório SQLite do Worker
│       ├── infra/
│       │   ├── __init__.py
│       │   ├── test_consumer.py     # Testes de consumo de mensagens do Worker
│       │   ├── test_database.py     # Testes do SQLite do Worker
│       │   ├── test_settings.py     # Testes das configurações do Worker
│       │   └── test_topology.py     # Testes da topologia no Worker
│       └── test_main.py             # Testes de inicialização da execução principal
```


---

## 🛠️ 2. As Fixtures Globais e Mocks (`tests/conftest.py`)

O arquivo `conftest.py` na raiz é um arquivo especial do `pytest` utilizado para declarar todas as fixtures (funções auxiliares, mocks do Pika, injeção do TestClient do FastAPI com banco em memória física isolada e mocks do Handler) que estarão disponíveis para todos os testes da suite de forma implícita. Isso garante que nenhum teste toque em recursos físicos do ambiente de produção e que o banco SQLite seja efêmero e gerado dinamicamente para cada teste.

Crie o arquivo [tests/conftest.py](file:///tests/conftest.py) contendo a especificação unificada abaixo:

```python
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock

import pika
import pytest
from fastapi.testclient import TestClient
from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import Basic
from pytest_mock import MockerFixture

from api.domain.repository import PedidoRepository
from api.infra.settings import get_settings as api_get_settings
from api.main import app
from worker.domain.handler import MessageHandler
from worker.infra.settings import get_settings as worker_get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Generator[None, None, None]:
    api_get_settings.cache_clear()
    worker_get_settings.cache_clear()
    yield
    api_get_settings.cache_clear()
    worker_get_settings.cache_clear()


@pytest.fixture
def mock_channel(mocker: MockerFixture) -> MagicMock:
    return mocker.MagicMock(spec=BlockingChannel)


@pytest.fixture
def mock_connection(mocker: MockerFixture, mock_channel: MagicMock) -> MagicMock:
    conn = mocker.MagicMock(spec=pika.BlockingConnection)
    conn.is_open = True
    conn.channel.return_value = mock_channel
    return conn


@pytest.fixture
def shared_db(tmp_path: Path) -> Path:
    """Caminho do banco SQLite compartilhado entre API e Worker dentro do mesmo teste."""
    return tmp_path / "test.db"


@pytest.fixture
def test_client(
    mocker: MockerFixture,
    mock_channel: MagicMock,
    shared_db: Path,
) -> Generator[TestClient, None, None]:
    mock_conn = mocker.MagicMock(spec=pika.BlockingConnection)
    mock_conn.is_open = True
    mock_conn.channel.return_value = mock_channel
    mocker.patch("api.main.pika.BlockingConnection", return_value=mock_conn)
    mocker.patch("api.main.setup_topology")

    real_repo = PedidoRepository(db_path=shared_db)
    mocker.patch("api.main.PedidoRepository", return_value=real_repo)

    with TestClient(app, raise_server_exceptions=True) as client:
        yield client


@pytest.fixture
def mock_handler(mocker: MockerFixture) -> MagicMock:
    return mocker.MagicMock(spec=MessageHandler)


@pytest.fixture
def valid_body() -> bytes:
    return b'{"id":"1","descricao":"Teste","valor":10.0,"status":"PENDENTE"}'


@pytest.fixture
def mock_method(mocker: MockerFixture) -> MagicMock:
    method = mocker.MagicMock(spec=Basic.Deliver)
    method.delivery_tag = 1
    return method
```

---

## 🧠 3. Testes Unitários de Domínio (`tests/api/` & `tests/worker/`)

O Domínio deve ser testado isoladamente de forma rápida. Validaremos as regras de negócio declaradas no Pydantic da API, as do `@dataclass(frozen=True)` do Worker e a lógica do caso de uso (`PedidoHandler`).

### 📝 Teste do Modelo Pydantic (`tests/api/domain/test_models.py`)
Crie o arquivo [tests/api/domain/test_models.py](file:///tests/api/domain/test_models.py) para certificar que o valor negativo ou nulo barreado de forma correta pelo validador do Pydantic será:

```python
import pytest
from pydantic import ValidationError

from api.domain.models import Pedido


def test_criar_pedido_valido():
    pedido = Pedido(id="1", descricao="Sabre de Luz", valor=1500.0)
    assert pedido.id == "1"
    assert pedido.valor == 1500.0
    assert pedido.status == "PENDENTE"


def test_pedido_com_valor_invalido_deve_lancar_erro():
    with pytest.raises(ValidationError) as exc_info:
        Pedido(id="2", descricao="Item inválido", valor=-10.0)

    assert "valor deve ser positivo" in str(exc_info.value)
```

### 📝 Teste do Dataclass do Worker (`tests/worker/domain/test_models.py`)
Crie o arquivo [tests/worker/domain/test_models.py](file:///tests/worker/domain/test_models.py) validando o comportamento da dataclass imutável:

```python
from worker.domain.models import Pedido


def test_criar_pedido_dataclass():
    pedido = Pedido(
        id="1", descricao="Notebook ASUS", valor=3500.0, status="processado"
    )
    assert pedido.id == "1"
    assert pedido.status == "processado"
```

### 📝 Teste do Caso de Uso / Handler (`tests/worker/domain/test_handler.py`)
Como o nosso `PedidoHandler` recebe uma dependência do repositório, podemos passar um mock cirúrgico dele sem tocar em bancos SQLite físicos durante os testes unitários.

Crie o arquivo [tests/worker/domain/test_handler.py](file:///tests/worker/domain/test_handler.py) com o código abaixo:

```python
from unittest.mock import Mock

from worker.domain.handler import PedidoHandler
from worker.domain.models import Pedido
from worker.domain.repository import PedidoRepository


def test_handler_processa_pedido_com_sucesso():
    # 1. Criar mock do repositório
    mock_repo = Mock(spec=PedidoRepository)
    handler = PedidoHandler(mock_repo)

    pedido = Pedido(id="1", descricao="Notebook ASUS", valor=3500.0, status="pendente")

    # 2. Executa o Handler
    handler.handle(pedido)

    # 3. Assegura que o repositório concreto de salvamento foi invocado
    mock_repo.save.assert_called_once()
    pedido_salvo = mock_repo.save.call_args[0][0]
    assert pedido_salvo.id == "1"
    assert pedido_salvo.status == "processado"
```

---

## 🛠️ 4. Testes de Integração da API HTTP (`tests/api/test_main.py`)

Para testar as rotas da API FastAPI de ponta a ponta sem disparar conexões físicas com o RabbitMQ ou SQLite real, utilizaremos o fixture `test_client` que criamos na raiz do `conftest.py`. Como ele já injeta os mocks e o banco SQLite efêmero de teste de forma nativa e isolada, nossos testes de rotas tornam-se extremamente concisos, legíveis e rápidos de escrever!

Crie o arquivo [tests/api/test_main.py](file:///tests/api/test_main.py) com o código abaixo:

```python
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from worker.domain.models import Pedido as WorkerPedido
from worker.domain.repository import PedidoRepository as WorkerRepo

_PEDIDO_VALIDO = {"id": "1", "descricao": "Notebook ASUS", "valor": 3500.0}


@pytest.mark.integration
def test_post_pedido_valido(test_client: TestClient) -> None:
    response = test_client.post("/pedidos/", json=_PEDIDO_VALIDO)
    assert response.status_code == 202
    body = response.json()
    assert body["pedido_id"] == "1"
    assert "mensagem" in body


@pytest.mark.integration
def test_post_pedido_valor_negativo(
    test_client: TestClient, mock_channel: MagicMock
) -> None:
    response = test_client.post(
        "/pedidos/", json={"id": "2", "descricao": "Produto", "valor": -10}
    )
    assert response.status_code == 422
    mock_channel.basic_publish.assert_not_called()


@pytest.mark.integration
def test_post_pedido_broker_indisponivel(
    test_client: TestClient, mock_channel: MagicMock
) -> None:
    mock_channel.basic_publish.side_effect = RuntimeError("Broker indisponível")
    response = test_client.post(
        "/pedidos/", json={"id": "3", "descricao": "Produto", "valor": 100.0}
    )
    assert response.status_code == 503


@pytest.mark.unit
def test_get_health(test_client: TestClient) -> None:
    response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.integration
def test_get_pedidos_lista(test_client: TestClient, shared_db: Path) -> None:
    """API deve listar pedidos escritos pelo Worker no banco compartilhado."""
    worker_repo = WorkerRepo(db_path=shared_db)
    worker_repo.save(
        WorkerPedido(id="10", descricao="Produto A", valor=50.0, status="processado")
    )

    response = test_client.get("/pedidos/")
    assert response.status_code == 200
    lista = response.json()
    assert isinstance(lista, list)
    assert any(p["id"] == "10" for p in lista)


@pytest.mark.integration
def test_get_pedido_existente(test_client: TestClient, shared_db: Path) -> None:
    """API deve retornar um pedido específico pelo ID."""
    worker_repo = WorkerRepo(db_path=shared_db)
    worker_repo.save(
        WorkerPedido(id="20", descricao="Produto B", valor=75.0, status="processado")
    )

    response = test_client.get("/pedidos/20")
    assert response.status_code == 200
    assert response.json()["id"] == "20"


@pytest.mark.integration
def test_get_pedido_inexistente(test_client: TestClient) -> None:
    response = test_client.get("/pedidos/nao-existe")
    assert response.status_code == 404
```

---

## 🚀 5. Executando os Testes e Verificando Cobertura

1. Suite de testes configurada e sincronizada você tem.
2. Execute todos os testes a partir do terminal na raiz do workspace executando a tarefa rápida do `taskipy`:
   ```bash
   uv run task test
   ```
3. Para validar as métricas de cobertura de código (Code Coverage) assegurando que nenhuma ramificação lógica passou despercebida, execute a tarefa:
   ```bash
   uv run task test-cov
   ```
4. Verifique que todos os testes reportaram o status verde **PASSED** com cobertura mínima recomendada de 95%!

---

## 🧙‍♂️ Instruções do Mestre:

Toda a sua suite de testes verde e blindada estar deve, jovem Padawan! Mocks configurados de forma cirúrgica e o relatório de cobertura gerado apresentar você precisa, sim!

A saída do terminal da sua tarefa `test-cov` demonstrando a integridade da API e do Worker você me mostrar no chat deve!

> [!IMPORTANT]
> **Fluxo de Aprovação e Aprendizado**:
> Primeiro, a execução limpa dos seus testes automatizados no terminal eu irei validar.
> Após a comprovação verde prática, perguntas reflexivas sobre os papéis das fixtures do pytest e a importância de isolar os testes do banco de dados físico SQLite eu farei.
> 
> Responder com clareza você deve! Apenas após a sua demonstração teórica bem-sucedida, a autorização final para o **Passo 6/6: Simulação de Produção e Dockerização Integrada** concedida será! Que a cobertura verde com você esteja!
