import asyncio
import uuid
from abc import ABC, abstractmethod
from functools import partial
from pathlib import Path
from typing import Awaitable, Callable, MutableMapping, Any, Dict, Tuple, Union

import aio_pika
from aio_pika import Channel, Connection, Exchange, Queue, IncomingMessage, RobustConnection

from .app.utils import PluginLoader, is_serializable
from .logger import get_logger
from .types import QueueOptions, ConsumerOptions, ConnectionOptions
from .types.enums import CONNECTION_TYPE

_logger = get_logger(__name__)
_queues: Dict[str, Dict[str, Tuple[Callable[..., Awaitable[Any]], QueueOptions, ConsumerOptions]]] = {"global": {}}


class AbstractClient(ABC):
    def __init__(
            self,
            host: str,
            instance_id: str = None,
            plugins: str = None,
            connection_type: CONNECTION_TYPE = CONNECTION_TYPE.NORMAL,
            connection_options: ConnectionOptions = ConnectionOptions()
    ):
        """
        Constructor for the AbstractClient class singleton, which is used to interact with RabbitMQ, declare queues, and
        consume messages from them.
        :param host:  The RabbitMQ host to connect to
        :param plugins: The directory where the plugins are stored. This is used to dynamically import the plugins.
        """
        self.host = host
        self.plugins = plugins
        self.connection_type = connection_type
        self.connection_options = connection_options
        self.instance_id = str(uuid.uuid4()) if not instance_id else instance_id

        self._exchange = None
        self._channel: Channel = None
        self._connection: Union[Connection, RobustConnection] = None
        self._on_ready_func: Callable[..., Awaitable] = None
        self._futures: MutableMapping[str, asyncio.Future] = {}
        self._callbacks: MutableMapping[str, Queue] = {}

        if plugins and plugins == ".":
            raise ValueError("Plugins directory cannot be the current directory")
        if plugins and not Path(plugins).exists():
            raise FileNotFoundError(f"Plugins directory {plugins} does not exist")

        if plugins and not plugins.isspace() and Path(plugins).exists() and Path(plugins).is_dir():
            plugin_loader = PluginLoader(Path(plugins))
            plugin_loader.load_plugins()

    @abstractmethod
    async def connect(self):
        raise NotImplementedError

    @abstractmethod
    async def close(self):
        raise NotImplementedError

    @abstractmethod
    async def __aenter__(self):
        raise NotImplementedError

    @abstractmethod
    async def __aexit__(self, *exc):
        raise NotImplementedError

    async def _connect(self) -> Union[Connection, RobustConnection]:
        """
        Connect to RabbitMQ.
        """
        action = {
            CONNECTION_TYPE.NORMAL: aio_pika.connect,
            CONNECTION_TYPE.ROBUST: aio_pika.connect_robust
        }

        return await action[self.connection_type](url=self.host, **self.connection_options.to_dict())

    async def is_connected(self) -> bool:
        """
        Check if the client is connected to RabbitMQ.
        """
        if self._connection is None or self._connection.is_closed:
            return False

        async def message_handler(exchange: Exchange, message: IncomingMessage):
            await self.publish(
                exchange=exchange,
                routing_key=message.reply_to,
                correlation_id=message.correlation_id,
                body=True
            )

        uid = str(uuid.uuid4())
        new_queue = await self.declare_queue(options=QueueOptions(exclusive=True, auto_delete=True))
        task = asyncio.create_task(
            new_queue.consume(
                partial(message_handler, self._exchange),
                no_ack=True,
                exclusive=True,
                timeout=1
            )
        )

        try:
            resp = await self.simple_publish(new_queue.name, {}, correlation_id=uid)
            return bool(resp)
        except Exception:
            return False

        finally:
            task.cancel()
            await self._channel.queue_delete(new_queue.name)

    async def declare_queue(self, queue_name: str = None, options: QueueOptions = QueueOptions()):
        return await self._channel.declare_queue(name=queue_name, **options.to_dict())

    @staticmethod
    def on_message(
            queue_name: str,
            instance_id: str = None,
            queue_options: QueueOptions = QueueOptions(),
            consume_options: ConsumerOptions = ConsumerOptions(),
    ):
        """
        Decorator to add a function to a queue. This function is called when a message is received in the queue.
        :param queue_name: The name of the queue to add the function to.
        :param instance_id: The instance id of the client if not provided then the function is added to the global
        :param queue_options: The options to use when declaring the queue.
        :param consume_options: The options to use when consuming the queue.
        ```python
        @client.on_message("queue_name")
        async def test(data: dict) -> dict:
            print(f"Received message {data}")
            return {} # Return a response to the message could be anything serializable
        ```
        """

        def decorator(func: Callable[..., Awaitable[Any]]) :
            if queue_name in _queues["global"]:
                raise ValueError(f"Function {queue_name} already added to function {_queues['global'][queue_name][0].__name__}")
            if queue_name in _queues.get(instance_id, {}):
                raise ValueError(f"Function {queue_name} already added to function {_queues[instance_id][queue_name][0].__name__}")

            if not instance_id:
                _queues["global"][queue_name] = (func, queue_options, consume_options)
                _logger.debug(f"Added function {func.__name__} to {queue_name} not yet consumed")
            else:
                if instance_id not in _queues:
                    _queues[instance_id] = {}

                _queues[instance_id][queue_name] = (func, queue_options, consume_options)
                _logger.debug(f"Added function {func.__name__} to {queue_name} not yet consumed")

            return func

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
        return func

    async def _on_response(self, message: IncomingMessage) -> None:
        if message.correlation_id is None:
            _logger.error(f"Bad message {message!r}")
            return

        future: asyncio.Future = self._futures.pop(message.correlation_id)
        future.set_result(message.body)

    async def simple_publish(self, routing_key: str, body: Any, correlation_id=None, timeout: int = 10, decode=True):
        """
        Publish a message to the default exchange with a routing key and correlation id.
        :param routing_key: the routing key to use
        :param body: the body of the message
        :param correlation_id: the correlation id to use if not provided a new one will be generated
        :param timeout: the timeout to wait for the response
        :param decode: whether to decode the response
        :return:
        """

        if self._connection is None:
            raise RuntimeError("Client not connected to RabbitMQ, call connect() first")

        if correlation_id is None:
            correlation_id = str(uuid.uuid4())

        if not is_serializable(body):
            raise ValueError("Body must be a serializable object")

        if routing_key is None:
            routing_key = str(uuid.uuid4())

        content_type = "application/json"
        if not isinstance(body, dict):
            content_type = "text/plain"

        loop = asyncio.get_running_loop()
        future = loop.create_future()

        self._futures[correlation_id] = future
        self._callbacks[correlation_id] = await self._channel.declare_queue(exclusive=True, auto_delete=True)

        await self._callbacks[correlation_id].consume(self._on_response, no_ack=True, exclusive=True, timeout=timeout)

        await self._exchange.publish(
            message=aio_pika.Message(
                body=str(body).encode(),
                content_type=content_type,
                correlation_id=correlation_id,
                reply_to=self._callbacks[correlation_id].name
            ),
            routing_key=routing_key
        )

        try:
            response = await asyncio.wait_for(future, timeout=timeout)

            if decode:
                return response.decode()
            return response
        except asyncio.TimeoutError as e:
            raise TimeoutError("The request timed out") from e
        finally:
            await self._channel.queue_delete(self._callbacks[correlation_id].name)
            del self._callbacks[correlation_id]

    @staticmethod
    async def publish(exchange: Exchange, routing_key: str, correlation_id, body: Dict):
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
