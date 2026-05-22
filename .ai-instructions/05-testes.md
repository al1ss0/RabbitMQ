# 🧪 Passo 5/6: Testes Automatizados, Mocks e Validação Arquitetural

Saudações, Padawan! Sua stack produtora e consumidora está de pé e rodando na rede Docker. No entanto, na Engenharia de Software de elite, nenhum código é considerado pronto sem **Testes Automatizados**.

Graças à nossa arquitetura em camadas do **DDD**, você descobrirá que testar a lógica do domínio é incrivelmente simples e rápido, pois ela não possui acoplamento com o RabbitMQ ou bancos concretos. Para testar a infraestrutura de mensagens, aprenderemos a utilizar **Mocks** de forma cirúrgica.

---

## 🧠 1. Testes Unitários de Domínio

O domínio deve ser testado isoladamente. Criaremos testes para validar as regras do nosso Modelo (`Pedido`) e do nosso Caso de Uso (`ProcessarPedidoHandler`).

### 📝 Teste do Modelo de Domínio (`tests/domain/test_models.py`)
Valide se as regras de validação do Pydantic barrarão valores negativos ou nulos de forma correta:
```python
import pytest
from pydantic import ValidationError
from api.domain.models import Pedido

def test_criar_pedido_valido():
    pedido = Pedido(id="123", descricao="Teclado Gamer", valor=250.0)
    assert pedido.id == "123"
    assert pedido.valor == 250.0

def test_pedido_com_valor_invalido_deve_lancar_erro():
    with pytest.raises(ValidationError) as exc_info:
        Pedido(id="123", descricao="Mouse Sem Fio", valor=-10.0)
    
    assert "valor deve ser positivo" in str(exc_info.value)
```

### 📝 Teste do Caso de Uso / Handler (`tests/domain/test_handler.py`)
Como nosso `ProcessarPedidoHandler` depende de uma interface abstrata (`PedidoProcessadoRepository`), podemos mocká-la facilmente usando `unittest.mock` sem tocar em arquivos locais:
```python
from unittest.mock import Mock
import pytest
from worker.domain.models import PedidoConsumido
from worker.domain.handler import ProcessarPedidoHandler
from worker.domain.repository import PedidoProcessadoRepository

def test_handler_processa_pedido_com_sucesso():
    # 1. Mockar o repositório de domínio
    mock_repo = Mock(spec=PedidoProcessadoRepository)
    handler = ProcessarPedidoHandler(mock_repo)
    pedido = PedidoConsumido(id="1", descricao="Processador Ryzen", valor=1200.0)

    # 2. Executar o Handler
    handler.handle(pedido)

    # 3. Assegurar que o repositório foi chamado com o pedido correto
    mock_repo.salvar_processado.assert_called_once_with(pedido)

def test_handler_lanca_erro_sob_item_invalido():
    mock_repo = Mock(spec=PedidoProcessadoRepository)
    handler = ProcessarPedidoHandler(mock_repo)
    pedido_ruim = PedidoConsumido(id="2", descricao="item inválido", valor=50.0)

    # O handler deve disparar uma exceção de negócio para que caia na DLX
    with pytest.raises(ValueError) as exc_info:
        handler.handle(pedido_ruim)

    assert "Falha de validação do domínio" in str(exc_info.value)
    mock_repo.salvar_processado.assert_not_called()
```

---

## 🛠️ 2. Testes de Infraestrutura (Mockando o Broker AMQP)

Para testarmos as rotas da nossa API sem precisar levantar o RabbitMQ físico localmente, vamos mockar a conexão de canal do Pika usando o mecanismo de dependência do FastAPI.

### 📝 Teste da Rota da API (`tests/infra/test_api.py`)
```python
from unittest.mock import Mock
from fastapi.testclient import TestClient
import pytest
from api.main import app, get_publisher
from api.infra.publisher import RabbitMQPublisher

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_criar_pedido_com_sucesso_via_api():
    # 1. Mockar o canal e o Publisher do RabbitMQ
    mock_channel = Mock()
    mock_publisher = RabbitMQPublisher(mock_channel)
    
    # 2. Sobrescrever a dependência do FastAPI para retornar nosso mock
    app.dependency_overrides[get_publisher] = lambda: mock_publisher

    payload = {"id": "10", "descricao": "Cadeira Gamer", "valor": 850.0}
    
    # 3. Disparar a requisição POST
    response = client.post("/pedidos/", json=payload)
    
    # 4. Asserções
    assert response.status_code == 202
    assert response.json()["mensagem"] == "Pedido enfileirado"
    
    # Limpar as dependências após o teste
    app.dependency_overrides.clear()
```

---

## 🛡️ O Selo de Qualidade do Mestre
> [!IMPORTANT]
> **Por que Testes com Mocks são cruciais no CI/CD?**
> Testar infraestruturas reais (como bancos físicos ou brokers) em ambientes de Integração Contínua (CI) pode ser extremamente instável, gerando lentidão e falsos-positivos por latência de rede.
> 
> A separação limpa proposta pelo **DDD** nos permite rodar testes unitários em milissegundos. Deixamos os testes que de fato dependem de conexões reais apenas para a fase final de **Testes de Integração** ou **Simulação de Produção**.

---

### 🧙‍♂️ Instruções do Mestre:
Escreva a suite de testes no diretório `tests/`, configure os mocks e assegure-se de que sua aplicação seja coberta por testes impecáveis.

> [!IMPORTANT]
> Quando finalizar os testes, converse comigo.
> Prepare-se para explicar: **como o desacoplamento do DDD facilitou a testabilidade do seu domínio**.
> Após responder satisfatoriamente, atualizarei seu progresso para `83% - Passo 6/6: Simulação e Documentação`.
