import json
import time


def handle_message(body: bytes) -> None:
    payload = json.loads(body)
    print("[worker] processando:", payload)
    time.sleep(1)
