import importlib.util
from pathlib import Path
from typing import Awaitable, Callable

import aio_pika

from .logger import get_logger

_logger = get_logger(__name__)
_queues: dict[str, Callable[..., Awaitable[None]]] = {}


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class PluginLoader:
    def __init__(self, plugins_dir: Path):
        self.plugins_dir = plugins_dir

    def load_plugins(self):
        for file in self.plugins_dir.iterdir():
            if file.suffix == ".py":
                spec = importlib.util.spec_from_file_location(file.stem, file)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)


class AbstractClient(metaclass=Singleton):
    def __init__(self, host: str, plugins: str = None):
        """
        Constructor for the AbstractClient class singleton, which is used to interact with RabbitMQ, declare queues, and
        consume messages from them.
        :param host:  The RabbitMQ host to connect to
        :param plugins: The directory where the plugins are stored. This is used to dynamically import the plugins.
        """
        self.host = host
        self.plugins = plugins
        self._exchange = None
        self._channel: aio_pika.Channel = None
        self._connection: aio_pika.Connection = None
        self._on_ready_func: Callable[..., Awaitable] = None

        if plugins and plugins == ".":
            raise ValueError("Plugins directory cannot be the current directory")
        if plugins and not Path(plugins).exists():
            raise FileNotFoundError(f"Plugins directory {plugins} does not exist")

        if plugins and not plugins.isspace() and Path(plugins).exists() and Path(plugins).is_dir():
            plugin_loader = PluginLoader(Path(plugins))
            plugin_loader.load_plugins()

    async def connect(self):
        self._connection = await aio_pika.connect(self.host)
        self._channel = await self._connection.channel()
        self._exchange = self._channel.default_exchange
        return self._connection, self._channel

    async def close(self):
        await self._connection.close()

    async def declare_queue(self, queue_name: str, exclusive: bool = False, **kwargs):
        return await self._channel.declare_queue(queue_name, exclusive=exclusive, **kwargs)

    @staticmethod
    def on_message(queue_name: str):
        """
        Decorator to add a function to a queue. This function is called when a message is received in the queue.
        :param queue_name: The name of the queue to add the function to.
        ```python
        @client.on_message("queue_name")
        async def test(data: dict) -> dict:
            print(f"Received message {data}")
            return {} # Return a response to the message could be anything serializable
        ```
        """

        def decorator(func: Callable[..., Awaitable]):
            if queue_name in _queues:
                raise ValueError(f"Function {queue_name} already added to function {_queues[queue_name].__name__}")

            _queues[queue_name] = func
            _logger.debug(f"Added function {func.__name__} to {queue_name} not yet consumed")

        return decorator

    def on_ready(self, func: Callable[..., Awaitable[None]]):
        """
        Decorator to set the on_ready function. This function is called when the client is ready to consume messages.
        :param func: The function to call when the client is ready to consume messages.
        ```python
        @client.on_ready
        async def on_ready():
            print("[*] Waiting for messages. To exit press CTRL+C")
        ```
        """
        self._on_ready_func = func

    @staticmethod
    async def publish(exchange: aio_pika.Exchange, routing_key: str, correlation_id, body: dict):
        """
        Publish a message to an exchange with a routing key and correlation id.
        :param exchange: the exchange to publish the message to
        :param routing_key: the routing key to use
        :param correlation_id: the correlation id to use
        :param body: the body of the message
        :return:
        """
        return await exchange.publish(
            message=aio_pika.Message(
                body=str(body).encode(),
                correlation_id=correlation_id
            ),
            routing_key=routing_key
        )
