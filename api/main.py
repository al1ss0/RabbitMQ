from contextlib import asynccontextmanager
import json
import pika
from fastapi import FastAPI, Request, HTTPException

from api.domain.schemas import Pedido, PedidoProcessado
from api.infra import database as db
from api.infra.publisher import Publisher
from api.infra.topology import declare_topology


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    params = pika.ConnectionParameters(host="localhost")
    connection = pika.BlockingConnection(params)
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
    ok = publisher.publish("pedidos_exchange", routing_key="pedidos", body=pedido.model_dump())
    if not ok:
        raise HTTPException(status_code=500, detail="Falha ao publicar mensagem")
    return {"status": "accepted"}


@app.get("/pedidos", response_model=list[PedidoProcessado])
def listar_pedidos():
    return db.list_pedidos()


@app.get("/health")
def health():
    return {"status": "ok"}
