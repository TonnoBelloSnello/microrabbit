import ast
import asyncio
import json
from functools import partial
from typing import Callable, Awaitable

from aio_pika import IncomingMessage, Exchange

from microrabbit.abc import AbstractClient, _queues, _logger, _is_serializable


class Client(AbstractClient):
    def __init__(self, host: str, plugins: str = None):
        """
        Constructor for the AbstractClient class singleton, which is used to interact with RabbitMQ, declare queues, and
        consume messages from them.
        :param host:  The RabbitMQ host to connect to
        :param plugins: The directory where the plugins are stored. This is used to dynamically import the plugins.
        """

        super().__init__(host, plugins)

    async def run(self) -> None:
        """
        Run the client, connect to RabbitMQ, declare the queues, and consume messages from them.
        """
        if not self._connection:
            await self.connect()

        tasks = []
        for queue_name, func in _queues.items():
            queue = await self.declare_queue(queue_name, exclusive=True)
            tasks.append(
                asyncio.create_task(queue.consume(partial(
                    self._handler,
                    self._exchange,
                    func
                )))
            )
            _logger.debug(f"Consuming function {func.__name__} from {queue_name}")

        if self._on_ready_func:
            await self._on_ready_func()

        await asyncio.Future()
        await asyncio.gather(*tasks)

    async def _handler(self, exchange: Exchange, function: Callable[..., Awaitable],
                       message: IncomingMessage) -> None:
        """
        Handle the incoming message, decode the body, and call the function with the data.
        :param exchange: The exchange to publish the response to
        :param function: The function to call with the data
        :param message: The incoming message
        """
        await message.ack()

        body = message.body.decode()
        data = ast.literal_eval(body)

        _logger.debug(f"Received message {data} from {message.routing_key}")

        returned = await function(data)

        if not _is_serializable(returned):
            raise ValueError("Function must return a serializable object")

        if returned:
            await self.publish(
                exchange=exchange,
                routing_key=message.reply_to,
                correlation_id=message.correlation_id,
                body=returned
            )
