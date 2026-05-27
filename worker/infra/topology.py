import pika


def setup_topology(channel: pika.adapters.blocking_connection.BlockingChannel) -> None:
    channel.exchange_declare(
        exchange="pedidos_exchange",
        exchange_type="topic",
        durable=True,
    )

    channel.exchange_declare(
        exchange="dlx_exchange",
        exchange_type="direct",
        durable=True,
    )

    channel.queue_declare(queue="dlx_pedidos", durable=True)
    channel.queue_bind(
        queue="dlx_pedidos",
        exchange="dlx_exchange",
        routing_key="pedidos.novo",
    )

    channel.queue_declare(
        queue="pedidos_queue",
        durable=True,
        arguments={"x-dead-letter-exchange": "dlx_exchange"},
    )
    channel.queue_bind(
        queue="pedidos_queue",
        exchange="pedidos_exchange",
        routing_key="pedidos.*",
    )