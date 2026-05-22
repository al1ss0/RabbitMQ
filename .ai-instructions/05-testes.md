# 🧪 Passo 5/6: Testes Automatizados, Mocks e Validação de Qualidade

Saudações, Padawan! Sua stack produtora e consumidora está de pé e rodando na rede local de forma funcional. No entanto, na Engenharia de Software profissional de elite, nenhum código é considerado pronto sem **Testes Automatizados**.

Graças à nossa arquitetura em camadas do **DDD**, você descobrirá que testar a lógica do domínio é incrivelmente simples e rápido, pois ela não possui qualquer acoplamento com o RabbitMQ ou bancos concretos. Para testarmos a infraestrutura (como as rotas da API) sem dependermos do Broker ligado, aprenderemos a utilizar **Mocks** de forma cirúrgica.

---

## 🏗️ 1. Estruturando a Pasta de Testes

Na raiz do seu workspace (`rabbitmq-stack/`), crie a estrutura de diretórios para a nossa suite de testes:

```
rabbitmq-stack/
├── tests/
│   ├── __init__.py
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── test_models.py       # Testes unitários das entidades de domínio
│   │   └── test_handler.py      # Testes unitários do caso de uso (handler)
│   └── infra/
│       ├── __init__.py
│       └── test_api.py          # Testes com Mocks da API FastAPI
```

---

## 🧠 2. Testes Unitários de Domínio (`tests/domain/`)

O Domínio deve ser testado isoladamente. Criaremos testes para validar as regras do nosso Modelo (`Pedido`) e do nosso Caso de Uso (`ProcessarPedidoHandler`).

### 📝 Teste do Modelo de Domínio (`tests/domain/test_models.py`)
Valide se as regras de validação do Pydantic barrarão valores negativos ou nulos de forma correta:

```python
import pytest
from pydantic import ValidationError
from api.domain.models import Pedido

def test_criar_pedido_valido():
    pedido = Pedido(id="ped-123", descricao="Sabre de Luz", valor=1500.0)
    assert pedido.id == "ped-123"
    assert pedido.valor == 1500.0

def test_pedido_com_valor_negativo_deve_lancar_erro():
    with pytest.raises(ValidationError) as exc_info:
        Pedido(id="ped-123", descricao="Cristal Kyber Defeituoso", valor=-50.0)
    
    assert "valor do pedido deve ser maior que zero" in str(exc_info.value)
```

### 📝 Teste do Caso de Uso / Handler (`tests/domain/test_handler.py`)
Como nosso `ProcessarPedidoHandler` depende de uma interface abstrata (`PedidoProcessadoRepository`), podemos mocká-la facilmente usando `unittest.mock` sem tocar em arquivos locais ou precisar do banco físico ativo:

```python
from unittest.mock import Mock
import pytest
from worker.domain.models import PedidoConsumido
from worker.domain.handler import ProcessarPedidoHandler
from worker.domain.repository import PedidoProcessadoRepository

def test_handler_processa_pedido_com_sucesso():
    # 1. Mockar a dependência do repositório de domínio
    mock_repo = Mock(spec=PedidoProcessadoRepository)
    handler = ProcessarPedidoHandler(mock_repo)
    pedido = PedidoConsumido(id="ped-001", descricao="Droide R2D2", valor=5000.0)

    # 2. Executa o Handler
    handler.handle(pedido)

    # 3. Assegura que o repositório concreto foi chamado exatamente com o pedido correto
    mock_repo.salvar_processado.assert_called_once_with(pedido)

def test_handler_lanca_erro_sob_item_invalido():
    mock_repo = Mock(spec=PedidoProcessadoRepository)
    handler = ProcessarPedidoHandler(mock_repo)
    pedido_ruim = PedidoConsumido(id="ped-999", descricao="item inválido", valor=10.0)

    # O handler deve disparar uma exceção de negócio para que caia na DLX
    with pytest.raises(ValueError) as exc_info:
        handler.handle(pedido_ruim)

    assert "Falha de validação do domínio" in str(exc_info.value)
    mock_repo.salvar_processado.assert_not_called()
```

---

## 🛠️ 3. Testes da Infraestrutura com Mocking (`tests/infra/`)

Para testarmos as rotas da nossa API sem precisar levantar o RabbitMQ físico ou de rede durante a execução dos testes automatizados de CI/CD, vamos mockar o Publisher do RabbitMQ substituindo a dependência no FastAPI.

### 📝 Teste das Rotas HTTP da API (`tests/infra/test_api.py`)

```python
from unittest.mock import Mock
from fastapi.testclient import TestClient
import pytest
from api.main import app, get_publisher
from api.infra.publisher import RabbitMQPublisher

client = TestClient(app)

def test_health_check_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_criar_pedido_com_sucesso_mockado():
    # 1. Mockar o canal do RabbitMQ e criar o publisher com o mock
    mock_channel = Mock()
    mock_publisher = RabbitMQPublisher(mock_channel)
    
    # 2. Injeta o mock substituindo a dependência do get_publisher no FastAPI
    app.dependency_overrides[get_publisher] = lambda: mock_publisher

    payload = {"id": "ped-10", "descricao": "Capacete de Beskar", "valor": 850.0}
    
    # 3. Dispara a requisição HTTP POST
    response = client.post("/pedidos/", json=payload)
    
    # 4. Asserções de integridade
    assert response.status_code == 202
    assert response.json()["status"] == "Pedido Aceito e Enfileirado"
    assert response.json()["pedido_id"] == "ped-10"
    
    # 5. Limpa as dependências sobrescritas
    app.dependency_overrides.clear()
```

---

## 🚀 4. Executando os Testes localmente

1. Para rodar a suite de testes, instale o `pytest` e a biblioteca `httpx` (requerida pelo FastAPI `TestClient` para comunicação http simulada):
   ```bash
   pip install pytest httpx
   ```
2. Adicione na raiz do projeto o arquivo `pytest.ini` ou rode os testes informando o caminho do projeto no Python Path para que os arquivos locais sejam encontrados:
   ```bash
   PYTHONPATH=. pytest -v
   ```
3. Garanta que todos os testes passem com status **PASSED**!

---

### 🧙‍♂️ Instruções do Mestre:
Escreva a suite de testes no diretório `tests/`, configure os mocks e assegure-se de que toda a lógica crítica da aplicação esteja coberta por testes impecáveis.

> [!IMPORTANT]
> Quando todos os testes unitários e de integração mockada passarem com status **GREEN**, compartilhe o terminal de execução e os arquivos de teste comigo no chat.
> 
> Como mentor, vou lhe auxiliar na correta configuração do Python Path e na estruturação do `pytest`. **Após validarmos os testes, farei 2 a 3 perguntas reflexivas sobre o papel do Mocking e como o desacoplamento de DDD facilitou nossa vida nos testes de domínio** antes de avançarmos o seu progresso para `83% - Passo 6/6: Simulação de Produção e Dockerização Integrada`.
