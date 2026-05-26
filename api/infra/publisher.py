import json
import pika
from typing import Any


class Publisher:
    def __init__(self, connection: pika.BlockingConnection, channel: pika.adapters.blocking_connection.BlockingChannel):
        self.connection = connection
        self.channel = channel
        try:
            self.channel.confirm_delivery()
        except Exception:
            pass

    def publish(self, exchange: str, routing_key: str, body: Any) -> bool:
        properties = pika.BasicProperties(content_type="application/json", delivery_mode=2)
        if isinstance(body, (dict, list)):
            body = json.dumps(body)
        try:
            result = self.channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=body,
                properties=properties,
            )
            return True if result is None else bool(result)
        except Exception as e:
            print(f"ERRO AO PUBLICAR: {e}")
            return False