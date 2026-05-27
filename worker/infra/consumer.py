import json
import time

from worker.infra.database import save_pedido


def handle_message(body: bytes) -> dict[str, object]:
    payload = json.loads(body)
    print("[worker] processando:", payload)
    time.sleep(1)
    save_pedido(payload, status="processado")
    return payload
