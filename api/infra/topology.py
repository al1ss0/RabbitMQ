import pika


def declare_topology(channel: pika.adapters.blocking_connection.BlockingChannel) -> None:
    channel.exchange_declare(exchange="pedidos_exchange", exchange_type="direct", durable=True)
    channel.queue_declare(queue="pedidos_queue", durable=True)
    channel.queue_bind(exchange="pedidos_exchange", queue="pedidos_queue", routing_key="pedidos")
