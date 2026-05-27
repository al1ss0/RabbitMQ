from typing import Optional

from pydantic import BaseModel


class Pedido(BaseModel):
    id: str
    item: str
    quantidade: int


class PedidoProcessado(Pedido):
    status: str
    received_at: str
    processed_at: Optional[str] = None
