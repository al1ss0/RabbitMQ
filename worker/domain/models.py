from dataclasses import dataclass


@dataclass(frozen=True)
class Pedido:
    id: str
    descricao: str
    valor: float
    status: str