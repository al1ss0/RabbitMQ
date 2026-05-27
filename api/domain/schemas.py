from typing import Optional
from pydantic import BaseModel, field_validator


class Pedido(BaseModel):
    id: str
    descricao: str
    valor: float

    @field_validator("valor")
    @classmethod
    def valor_deve_ser_positivo(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("valor deve ser maior que zero")
        return v


class PedidoProcessado(Pedido):
    status: str
    received_at: str
    processed_at: Optional[str] = None