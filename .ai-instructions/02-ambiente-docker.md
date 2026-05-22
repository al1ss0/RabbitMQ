# 🐳 Passo 2/6: Ambiente de Orquestração — Setup do Workspace & RabbitMQ Broker

Saudações, Padawan! Agora que você dominou os alicerces conceituais e a arquitetura em camadas do nosso sistema, iniciaremos a jornada prática.

Neste passo, nosso objetivo é preparar a estrutura física de diretórios do nosso projeto e subir o **RabbitMQ Broker** em container de forma isolada. Isso garantirá que tenhamos um servidor de mensageria ativo na sua máquina local pronto para aceitar conexões TCP enquanto desenvolvemos a API e o Worker nos próximos passos.

---

## 🏗️ 1. Preparando a Estrutura de Diretórios

Antes de escrever qualquer código ou configuração Docker, crie a seguinte estrutura física de diretórios no seu espaço de trabalho. Ela reflete a separação estrita de escopos da nossa stack:

```
rabbitmq-stack/
├── api/                  # 📡 Código-fonte da API FastAPI
│   ├── domain/           # Camada de Domínio (Contratos e Modelos)
│   └── infra/            # Camada de Infraestrutura (Implementações concretas)
├── worker/               # ⚙️ Código-fonte do Worker Consumidor Pika
│   ├── domain/           # Camada de Domínio do Worker
│   └── infra/            # Camada de Infraestrutura do Worker
├── data/                 # 📂 Pasta local para persistência de dados físicos (banco JSON)
└── docker-compose.yml    # 🐳 Orquestração do nosso ambiente Docker
```

> [!TIP]
> Crie as pastas vazias primeiro. Não se preocupe em criar arquivos de código Python (`.py`) ainda. Faremos isso de forma guiada no momento certo.

---

## 🐳 2. O Docker Compose do Broker

Na raiz do seu workspace (`rabbitmq-stack/`), crie o arquivo `docker-compose.yml` focado em expor o RabbitMQ de maneira robusta para desenvolvimento local.

Nesta etapa, o compose irá conter **apenas o serviço do RabbitMQ Broker**. Não adicionaremos os serviços da API ou do Worker ainda, pois os códigos de produção deles não existem e o build falharia.

Crie o arquivo [docker-compose.yml](file:///docker-compose.yml) com o seguinte blueprint:

```yaml
version: '3.8'

services:
  rabbitmq-broker:
    image: rabbitmq:3.12-management-alpine
    container_name: rabbitmq-broker
    ports:
      - "5672:5672"     # Porta padrão do protocolo AMQP (para conexões TCP da nossa app)
      - "15672:15672"   # Porta do painel de administração web (Management Console)
    environment:
      RABBITMQ_DEFAULT_USER: guest
      RABBITMQ_DEFAULT_PASS: guest
    healthcheck:
      # Verifica se o broker está totalmente ativo e pronto para conexões AMQP
      test: ["CMD-SHELL", "rabbitmq-diagnostics -q check_running"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - rabbitmq-network

networks:
  rabbitmq-network:
    driver: bridge
```

---

## ⚡ 3. Subindo o Broker e Validando

Com a estrutura de pastas criada e o `docker-compose.yml` salvo, abra o seu terminal na raiz do projeto e execute:

```bash
docker compose up -d rabbitmq-broker
```

Este comando fará o download da imagem leve baseada em Alpine e iniciará o container do broker em segundo plano.

### 🔍 Como validar que está tudo funcionando:
1. **Acesse o Management Console**: Abra o seu navegador e vá em [http://localhost:15672](http://localhost:15672).
2. **Faça o Login**: Utilize o usuário `guest` e a senha `guest` configurados no compose.
3. **Monitore o Healthcheck**: Execute o comando `docker ps` no seu terminal e verifique se o container `rabbitmq-broker` exibe o status `(healthy)` após alguns segundos de inicialização.

---

### 🧙‍♂️ Instruções do Mestre:
Prepare a estrutura de diretórios e crie o `docker-compose.yml` inicial conforme as especificações. 

> [!IMPORTANT]
> Quando a estrutura estiver montada e o RabbitMQ Broker estiver rodando localmente com status `(healthy)`, compartilhe comigo (o **Jedi da Mensageria** no chat) a árvore de diretórios que você criou e a confirmação de que acessou o painel de administração.
> 
> Como mentor, vou lhe auxiliar na estrutura inicial de pastas e conferir suas portas. **Após a sua validação, farei 2 a 3 perguntas reflexivas sobre redes no Docker e o papel do Healthcheck no Broker** antes de avançarmos o seu progresso para `33% - Passo 3/6: API Produtora FastAPI`.
