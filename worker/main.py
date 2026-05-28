import os
import time

import pika
from worker.infra.consumer import handle_message
from worker.infra.database import init_db
from worker.infra.topology import setup_topology


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
            print(f"[worker] aguardando broker RabbitMQ ({attempt}/10)...")
            time.sleep(3)


def on_message(ch, method, properties, body):
    try:
        handle_message(body)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as exc:
        print("[worker] erro ao processar:", exc)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def main() -> None:
    init_db()
    conn = get_rabbitmq_connection()
    channel = conn.channel()
    setup_topology(channel)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue="pedidos_queue", on_message_callback=on_message)
    print("[worker] aguardando mensagens...")
    channel.start_consuming()


if __name__ == "__main__":
    main()
