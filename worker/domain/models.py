from dataclasses import dataclass


@dataclass(frozen=True)
class Pedido:
    id: str
    item: str
    quantidade: int
