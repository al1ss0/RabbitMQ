import pika
from worker.infra.consumer import handle_message
from worker.infra.database import init_db
from worker.infra.topology import setup_topology


def on_message(ch, method, properties, body):
    try:
        handle_message(body)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as exc:
        print("[worker] erro ao processar:", exc)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def main() -> None:
    init_db()
    params = pika.ConnectionParameters(host="localhost")
    conn = pika.BlockingConnection(params)
    channel = conn.channel()
    setup_topology(channel)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue="pedidos_queue", on_message_callback=on_message)
    print("[worker] aguardando mensagens...")
    channel.start_consuming()


if __name__ == "__main__":
    main()