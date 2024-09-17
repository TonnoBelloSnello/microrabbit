import ast
import asyncio
from functools import partial
from typing import Callable, Awaitable, Union, Literal, List

from aio_pika import IncomingMessage, Exchange

from microrabbit.abc import AbstractClient, _queues, _logger
from microrabbit.types import ConnectionOptions
from microrabbit.types.enums import CONNECTION_TYPE
from .utils import is_serializable


class Client(AbstractClient):
    def __init__(
            self,
            host: str,
            instance_id: str = None,
            plugins: str = None,
            connection_type: Union[CONNECTION_TYPE, Literal["NORMAL", "ROBUST"]] = CONNECTION_TYPE.NORMAL,
            connection_options: ConnectionOptions = ConnectionOptions()
    ):
        """
        Constructor for the AbstractClient class singleton, which is used to interact with RabbitMQ, declare queues, and
        consume messages from them.
        :param host: The RabbitMQ host to connect to
        :param instance_id: The instance ID of the client to use. If not provided, a random UUID is generated.
        :param plugins: The directory where the plugins are stored. This is used to dynamically import the plugins.
        :param connection_type: The type of connection to use.
        :param connection_options: The connection options to use.
        """
        try:
            connection_type = CONNECTION_TYPE(connection_type)
        except ValueError:
            raise ValueError(f"Invalid connection type {connection_type}")

        super().__init__(host, instance_id, plugins, connection_type, connection_options)

    async def connect(self):
        self._connection = await self._connect()
        self._channel = await self._connection.channel()
        self._exchange = self._channel.default_exchange
        return self._connection, self._channel
    
    async def close(self):
        await self._connection.close()

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *exc):
        await self.close()
        return False

    async def run(self) -> None:
        """
        Run the client, connect to RabbitMQ, declare the queues, and consume messages from them.
        """
        if not self._connection:
            await self.connect()
        
        global_tasks = await self._create_queues("global", remove=True)
        instance_tasks = await self._create_queues(self.instance_id, remove=True) 

        if self._on_ready_func:
            await self._on_ready_func()

        await asyncio.Future()
        await asyncio.gather(*global_tasks, *instance_tasks)

    async def _handler(self, exchange: Exchange, function: Callable[..., Awaitable],
                       no_ack: bool, message: IncomingMessage) -> None:
        """
        Handle the incoming message, decode the body, and call the function with the data.
        :param exchange: The exchange to publish the response to
        :param function: The function to call with the data
        :param message: The incoming message
        """
        if not no_ack:
            await message.ack()

        body = message.body.decode()
        try:
            data = ast.literal_eval(body)
        except (SyntaxError, ValueError):
            data = body

        _logger.debug(f"Received message {data} from {message.routing_key}")

        returned = await function(data)

        if not is_serializable(returned):
            raise ValueError("Function must return a serializable object")

        if returned:
            await self.publish(
                exchange=exchange,
                routing_key=message.reply_to,
                correlation_id=message.correlation_id,
                body=returned
            )

    async def _create_queues(self, instance_id: str = None, remove: bool = False) -> List[asyncio.Task]:
        """
        Create the queues from the queues dictionary.
        :param queues: The queues dictionary
        """
        tasks = []
        queues = _queues.get(instance_id, {})
        for queue_name, func in queues.copy().items():
            queue = await self.declare_queue(queue_name, func[1])
            tasks.append(
                asyncio.create_task(queue.consume(
                    partial(
                        self._handler,
                        self._exchange,
                        func[0],
                        func[2].no_ack
                    ),
                    **func[2].to_dict()
                ))
            )
            _logger.debug(f"Consuming function {func[0].__name__} from {queue_name}")

            if remove:
                del _queues[instance_id][queue_name]
                
        return tasks