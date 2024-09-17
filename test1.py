import asyncio
import logging

from microrabbit import Client
from microrabbit.types import QueueOptions, ConsumerOptions, ConnectionOptions

client = Client(
    host="amqp://guest:guest@localhost/",
    connection_type="ROBUST",
    connection_options=ConnectionOptions()
)

log = logging.getLogger(__file__)
logging.basicConfig(level=logging.INFO)


@Client.on_message("queue_name")
async def test(data: dict) -> dict:
    log.info(f"Received message {data}")
    return {"connected": True}


@Client.on_message("queue_name2", queue_options=QueueOptions(exclusive=True), consume_options=ConsumerOptions(no_ack=True))
async def test2(data: dict) -> dict:
    log.info(f"Received message {data}")
    return {"connected": True}


@client.on_ready
async def on_ready():
    log.info("[*] Waiting for messages. To exit press CTRL+C")
    result = await client.simple_publish("queue_name2", {"test": "data"}, timeout=2, decode=True)
    log.info(result)


if __name__ == "__main__":
    asyncio.run(client.run())
