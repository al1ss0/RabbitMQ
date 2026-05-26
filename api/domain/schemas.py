from pydantic import BaseModel


class Pedido(BaseModel):
    id: str
    item: str
    quantidade: int
