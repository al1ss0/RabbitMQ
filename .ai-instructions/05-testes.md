# 🧪 Passo 5/6: Testes Automatizados, Mocks e Validação de Qualidade

Saudações, Padawan! A API e o seu Worker em rede local conversando e persistindo dados já estão! Orgulhoso do seu progresso na força eu estou, sim! No entanto, na Engenharia de Software profissional de elite, código sem **Testes Automatizados** considerado pronto nunca é!

Graças à nossa arquitetura em camadas do **DDD**, testar a lógica do domínio extremamente simples e rápido será, pois ela acoplamento físico com o RabbitMQ ou bancos concretos não possui! E para testarmos a infraestrutura e as rotas da nossa API sem dependermos do Broker ou banco físico ligados, fixtures de **Mocking** e bancos SQLite em memória ou temporários nós criaremos!

---

## 🏗️ 1. Estruturando a Pasta de Testes

No ecossistema unificado sincronizado com o `uv`, criaremos a nossa suite de testes. A estrutura completa e profissional de testes da nossa aplicação robusta idêntica à referência estar deve:

```
rabbitmq-stack/
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Fixtures globais de conexão/canal mockados
│   ├── api/
│   │   ├── __init__.py
│   │   ├── conftest.py          # Fixtures da API (test_client com DB temporário compartilhado)
│   │   ├── domain/
│   │   │   ├── __init__.py
│   │   │   ├── test_models.py       # Testes unitários do modelo Pydantic da API
│   │   │   └── test_repository.py   # Testes unitários do repositório da API (leitura/lista SQLite)
│   │   ├── infra/
│   │   │   ├── __init__.py
│   │   │   ├── test_database.py     # Testes da conexão e inicialização do SQLite na API
│   │   │   ├── test_publisher.py    # Testes de publicação de mensagens no RabbitMQ
│   │   │   ├── test_settings.py     # Testes de carregamento das configurações da API
│   │   │   └── test_topology.py     # Testes de setup da topologia AMQP
│   │   └── test_main.py             # Testes de integração das rotas HTTP (TestClient + Mocks)
│   └── worker/
│       ├── __init__.py
│       ├── conftest.py          # Fixtures do Worker (mock do handler, payloads e delivery tags)
│       ├── domain/
│       │   ├── __init__.py
│       │   ├── test_handler.py      # Testes unitários do PedidoHandler (casos de uso)
│       │   ├── test_models.py       # Testes unitários da Dataclass do Worker
│       │   └── test_repository.py   # Testes unitários do repositório do Worker (escrita SQLite)
│       ├── infra/
│       │   ├── __init__.py
│       │   ├── test_consumer.py     # Testes de consumo, tratamento de erros e acks/nacks
│       │   ├── test_database.py     # Testes de conexão SQLite do Worker
│       │   ├── test_settings.py     # Testes de carregamento das configurações do Worker
│       │   └── test_topology.py     # Testes de setup da topologia AMQP no Worker
│       └── test_main.py             # Testes de inicialização e tratamento gracioso do Worker
```

---

## 🛠️ 2. Fixtures Globais e Específicas do pytest

O `pytest` utiliza arquivos `conftest.py` para injetar dependências e mocks (fixtures) nos testes de forma limpa e modular. Criaremos as fixtures globais e locais da API e do Worker.

### 🌎 Fixture Global (`tests/conftest.py`)
Aqui mockaremos a biblioteca `pika` para que nenhuma conexão real seja disparada em testes unitários ou de integração básicos, e limparemos o cache das configurações de settings para evitar contaminação entre os testes.

Crie o arquivo [tests/conftest.py](file:///tests/conftest.py):

```python
from collections.abc import Generator
from unittest.mock import MagicMock

import pika
import pytest
from pika.adapters.blocking_connection import BlockingChannel
from pytest_mock import MockerFixture

from api.infra.settings import get_settings as api_get_settings
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
    conn.channel.return_value = mock_channel
    return conn
```

### 🔌 Fixtures Específicas da API (`tests/api/conftest.py`)
Para testarmos as rotas da API, precisamos de um banco de dados SQLite temporário e de um `TestClient` configurado com mocks apropriados do RabbitMQ para não disparar conexões reais.

Crie o arquivo [tests/api/conftest.py](file:///tests/api/conftest.py):

```python
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock

import pika
import pytest
from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from api.domain.repository import PedidoRepository
from api.main import app


@pytest.fixture
def shared_db(tmp_path: Path) -> Path:
    """Caminho do banco SQLite compartilhado entre API e Worker dentro do mesmo teste.

    Tanto o fixture `test_client` quanto os testes que precisam popular o banco
    via WorkerRepo devem usar este fixture — o acoplamento fica explícito.
    """
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
```

### ⚙️ Fixtures Específicas do Worker (`tests/worker/conftest.py`)
No Worker, precisamos testar o comportamento do consumo e handlers com payloads válidos e mocks de canais de entrega.

Crie o arquivo [tests/worker/conftest.py](file:///tests/worker/conftest.py):

```python
from unittest.mock import MagicMock

import pytest
from pika.spec import Basic
from pytest_mock import MockerFixture

from worker.domain.handler import MessageHandler


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

## 🧠 3. Testes Unitários de Domínio

Os testes unitários focam na lógica pura do domínio da nossa aplicação. Eles devem ser rápidos e independentes de serviços de infraestrutura.

### 📝 Teste do Modelo Pydantic da API (`tests/api/domain/test_models.py`)
Validaremos as regras de negócio declaradas no Pydantic da API.

Crie o arquivo [tests/api/domain/test_models.py](file:///tests/api/domain/test_models.py):

```python
import pytest
from pydantic import ValidationError

from api.domain.models import Pedido, PedidoResponse


@pytest.mark.unit
def test_pedido_cria_com_campos_validos() -> None:
    p = Pedido(id="1", descricao="Notebook", valor=3500.0)
    assert p.id == "1"
    assert p.descricao == "Notebook"
    assert p.valor == 3500.0
    assert p.status == "PENDENTE"


@pytest.mark.unit
def test_pedido_status_default_pendente() -> None:
    p = Pedido(id="1", descricao="Produto", valor=10.0)
    assert p.status == "PENDENTE"


@pytest.mark.unit
@pytest.mark.parametrize("valor", [0.0, -1.0, -100.0])
def test_pedido_valor_nao_positivo_levanta_validation_error(valor: float) -> None:
    with pytest.raises(ValidationError):
        Pedido(id="1", descricao="Produto", valor=valor)


@pytest.mark.unit
def test_pedido_response_cria_com_campos_corretos() -> None:
    r = PedidoResponse(mensagem="Pedido enfileirado", pedido_id="42")
    assert r.mensagem == "Pedido enfileirado"
    assert r.pedido_id == "42"
```

### 📝 Teste do Dataclass do Worker (`tests/worker/domain/test_models.py`)
Certificaremos que o nosso `@dataclass(frozen=True)` do Worker se comporta como uma entidade imutável de domínio.

Crie o arquivo [tests/worker/domain/test_models.py](file:///tests/worker/domain/test_models.py):

```python
from dataclasses import FrozenInstanceError

import pytest

from worker.domain.models import Pedido


@pytest.mark.unit
def test_pedido_cria_com_campos_corretos() -> None:
    p = Pedido(id="1", descricao="Produto", valor=10.0, status="PENDENTE")
    assert p.id == "1"
    assert p.descricao == "Produto"
    assert p.valor == 10.0
    assert p.status == "PENDENTE"


@pytest.mark.unit
def test_pedido_e_imutavel() -> None:
    p = Pedido(id="1", descricao="Produto", valor=10.0, status="PENDENTE")
    with pytest.raises(FrozenInstanceError):
        p.status = "processado"  # type: ignore[misc]
```

### 📝 Teste do Caso de Uso / Handler do Worker (`tests/worker/domain/test_handler.py`)
O `PedidoHandler` gerencia o ciclo do negócio e delega a gravação física ao `PedidoRepository`. Testaremos ele injetando um mock do repositório.

Crie o arquivo [tests/worker/domain/test_handler.py](file:///tests/worker/domain/test_handler.py):

```python
import pytest
from pytest_mock import MockerFixture

from worker.domain.handler import PedidoHandler
from worker.domain.models import Pedido
from worker.domain.repository import PedidoRepository


@pytest.fixture
def repository(mocker: MockerFixture) -> PedidoRepository:
    return mocker.MagicMock(spec=PedidoRepository)


@pytest.fixture
def pedido() -> Pedido:
    return Pedido(id="1", descricao="Teste", valor=10.0, status="PENDENTE")


@pytest.mark.unit
def test_pedido_handler_chama_save_com_status_processado(
    mocker: MockerFixture,
    repository: PedidoRepository,
    pedido: Pedido,
) -> None:
    mocker.patch("worker.domain.handler.time.sleep")
    handler = PedidoHandler(repository)
    handler.handle(pedido)

    repository.save.assert_called_once()
    pedido_salvo = repository.save.call_args.args[0]
    assert pedido_salvo.status == "processado"
    assert pedido_salvo.id == pedido.id


@pytest.mark.unit
def test_pedido_handler_repositorio_exception_propagada(
    mocker: MockerFixture,
    repository: PedidoRepository,
    pedido: Pedido,
) -> None:
    mocker.patch("worker.domain.handler.time.sleep")
    repository.save.side_effect = RuntimeError("Falha no repositório")
    handler = PedidoHandler(repository)

    with pytest.raises(RuntimeError, match="Falha no repositório"):
        handler.handle(pedido)
```

---

## 🛠️ 4. Testes de Integração da API HTTP (`tests/api/test_main.py`)

Para testar as rotas da API FastAPI de ponta a ponta, utilizaremos a fixture `test_client` definida em `tests/api/conftest.py` para isolar a infraestrutura real e interagir com o SQLite compartilhado em memória/temporário.

Crie o arquivo [tests/api/test_main.py](file:///tests/api/test_main.py):

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


@pytest.mark.integration
@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("valor", 0),
        ("valor", -1),
        ("id", None),
        ("descricao", None),
    ],
)
def test_post_pedido_payload_invalido(
    test_client: TestClient, campo: str, valor: object
) -> None:
    payload: dict[str, object] = {"id": "99", "descricao": "Produto", "valor": 10.0}
    payload[campo] = valor
    response = test_client.post("/pedidos/", json=payload)
    assert response.status_code == 422
```

---

## 🚀 5. Executando os Testes e Verificando Cobertura

1. Suite de testes configurada e sincronizada você tem!
2. Execute todos os testes a partir do terminal na raiz do workspace executando a tarefa rápida do `taskipy`:
   ```bash
   uv run task test
   ```
3. Para validar as métricas de cobertura de código (Code Coverage) assegurando que nenhuma ramificação lógica passou despercebida, execute a tarefa:
   ```bash
   uv run task test-cov
   ```
4. Verifique que todos os testes reportaram o status verde **PASSED** com cobertura mínima de 95%!

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
