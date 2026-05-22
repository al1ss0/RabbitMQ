# 🚀 Passo 6/6: Simulação de Carga, Monitoramento e Documentação

Parabéns pela resiliência, Padawan! Você chegou ao último passo. Sua stack está totalmente codificada, orquestrada via Docker Compose e testada com sucesso.

Agora, você aprenderá a validar o comportamento do sistema sob carga, monitorar a topologia e métricas do broker através da API de Gerenciamento do RabbitMQ e documentar seu projeto com maestria.

---

## 📡 1. Testando via REST Client (`requests.http`)

Para interagir com a sua stack sem precisar de um navegador ou terminal complexo, crie um arquivo chamado `requests.http` na raiz do seu projeto. Esse arquivo pode ser executado diretamente no VS Code com a extensão *REST Client*.

Ele cobrirá testes da API FastAPI e também chamadas na **Management HTTP API** do RabbitMQ (que expõe métricas das filas em tempo real).

```http
### Variáveis globais
@api = http://localhost:8000
@rmq = http://localhost:15672/api
@rmq_auth = Basic guest guest

# =============================================================================
# 1. Testando a API Produtora FastAPI
# =============================================================================

### 🟢 Health check
GET {{api}}/health

###

### 🔵 Criar Pedido Válido (HTTP 202 - Aceito e Enfileirado)
POST {{api}}/pedidos/
Content-Type: application/json

{
  "id": "1",
  "descricao": "Notebook Gamer Core i7",
  "valor": 4500.00
}

###

### 🔴 Criar Pedido com Valor Inválido (HTTP 422 - Rejeitado pela API/Pydantic)
POST {{api}}/pedidos/
Content-Type: application/json

{
  "id": "2",
  "descricao": "Mouse Pad",
  "valor": -15.00
}

###

### 🟡 Criar Pedido com Descrição Inválida (HTTP 202 aceito na API, mas deve ir para a DLX pelo Worker)
POST {{api}}/pedidos/
Content-Type: application/json

{
  "id": "3",
  "descricao": "item inválido",
  "valor": 100.00
}

###

### 🚀 Simular Concorrência: Enviar Pedidos em Lote (Fair Dispatch)
POST {{api}}/pedidos/
Content-Type: application/json

{
  "id": "10",
  "descricao": "Teclado Mecânico 10",
  "valor": 320.0
}
###
POST {{api}}/pedidos/
Content-Type: application/json

{
  "id": "11",
  "descricao": "Headset Gamer 11",
  "valor": 450.0
}
###
POST {{api}}/pedidos/
Content-Type: application/json

{
  "id": "12",
  "descricao": "Cadeira Ergonômica 12",
  "valor": 1200.0
}

# =============================================================================
# 2. Consultando Métricas e Topologia via API do RabbitMQ
# =============================================================================

### 📊 Visão geral de todas as filas
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

###

### 🔗 Bindings declarados entre Exchange e Fila
GET {{rmq}}/bindings/%2F/e/pedidos_exchange/q/pedidos_queue
Authorization: {{rmq_auth}}
```

---

## 📝 2. Estruturando a Documentação (`README.md`)

Todo grande arquiteto de software documenta o seu trabalho para que outros desenvolvedores possam executá-lo sem fricção. Seu `README.md` final deve ser extremamente premium e deve conter:

1. **Visão Geral e Arquitetura**: O diagrama de sequência e a explicação do fluxo assíncrono.
2. **Instruções de Inicialização**:
   - Como sincronizar dependências locais via `uv sync`.
   - Como subir o ambiente completo: `docker compose up --build`.
3. **Simulação Prática Passo a Passo**:
   - Como abrir os logs do worker em tempo real para assistir o consumo (`docker logs -f worker-consumidor`).
   - Como submeter os requests de teste descritos no arquivo `requests.http`.
   - Como verificar o painel visual administrativo do RabbitMQ em `http://localhost:15672` com credenciais `guest/guest`.
4. **Comportamento de Escalabilidade**:
   - Instrução de como escalar múltiplos consumidores paralelos para demonstrar o *Fair Dispatch* em ação:
     ```bash
     docker compose up --scale worker-consumidor=3 -d
     ```
5. **Comportamento de Falha (DLX)**:
   - Explicação de como o request de "item inválido" gera uma exceção no worker, que envia `basic_nack(requeue=False)` e direciona a mensagem automaticamente para a Dead Letter Queue (`dlx_pedidos`).

---

### 🧙‍♂️ Instruções do Mestre:
Crie o arquivo `requests.http` e elabore o seu `README.md` explicativo contendo todos os passos e cenários da simulação. 

> [!IMPORTANT]
> Quando terminar a estruturação e simulação, me chame no chat. 
> Mostre-me sua simulação funcionando e prepare-se:
> **Assim que validar a conclusão de todo o projeto (Progresso: 100%), apresentarei a você o QUIZ DE FIXAÇÃO FINAL!** 
> Ele testará se você de fato conquistou a maestria do design Event-Driven. Que a Força esteja com você!
