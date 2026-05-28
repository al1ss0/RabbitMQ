import os
import time
from contextlib import asynccontextmanager

import pika
from fastapi import FastAPI, Request, HTTPException

from api.domain.schemas import Pedido, PedidoProcessado
from api.infra import database as db
from api.infra.publisher import Publisher
from api.infra.topology import declare_topology


def get_rabbitmq_connection() -> pika.BlockingConnection:
    host = os.getenv("RABBITMQ_HOST", "localhost")
    port = int(os.getenv("RABBITMQ_PORT", "5672"))
    user = os.getenv("RABBITMQ_USER", "guest")
    password = os.getenv("RABBITMQ_PASSWORD", "guest")
    credentials = pika.PlainCredentials(user, password)
    params = pika.ConnectionParameters(host=host, port=port, credentials=credentials)

    for attempt in range(1, 11):
        try:
            return pika.BlockingConnection(params)
        except pika.exceptions.AMQPConnectionError:
            if attempt == 10:
                raise
            print(f"[api] aguardando broker RabbitMQ ({attempt}/10)...")
            time.sleep(3)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    connection = get_rabbitmq_connection()
    channel = connection.channel()
    declare_topology(channel)
    publisher = Publisher(connection, channel)
    app.state.publisher = publisher
    yield
    try:
        connection.close()
    except Exception:
        pass


app = FastAPI(lifespan=lifespan)


@app.post("/pedidos", status_code=202)
def criar_pedido(pedido: Pedido, request: Request):
    publisher: Publisher = request.app.state.publisher
    ok = publisher.publish("pedidos_exchange", routing_key="pedidos.novo", body=pedido.model_dump())
    if not ok:
        raise HTTPException(status_code=500, detail="Falha ao publicar mensagem")
    return {"status": "accepted"}


@app.get("/pedidos", response_model=list[PedidoProcessado])
def listar_pedidos():
    return db.list_pedidos()


@app.get("/health")
def health():
    return {"status": "ok"}