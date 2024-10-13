import ast
import asyncio
import inspect
import sys
from functools import partial
from typing import Callable, Awaitable, Union, Literal, List, get_origin, get_args, Dict, Any, Type

if sys.version_info >= (3, 10):
    from types import UnionType

from aio_pika import IncomingMessage, Exchange
from pydantic import ValidationError, BaseModel

from microrabbit.abc import AbstractClient, _queues, _logger
from microrabbit.types import ConnectionOptions
from microrabbit.types.enums import CONNECTION_TYPE
from .utils import is_serializable


def _params_dict(function: Callable[..., Awaitable]) -> Dict[str, List[Type]]:
    """
    Create the parameters for the on_message decorator.
    :param function: The function to call
    :return: The required parameters for the on_message decorator as a dictionary
    """

    params = inspect.signature(function).parameters
    params_dict = {}

    for param in params.values():
        if param.default is not param.empty:
            continue

        annotation = param.annotation
        origin = get_origin(annotation)
        if origin is Union or (sys.version_info >= (3, 10) and origin is UnionType):
            args = get_args(annotation)

            filtered_args = [arg for arg in args if arg is not type(None)]

            if filtered_args:
                params_dict[param.name] = filtered_args
        else:
            params_dict[param.name] = [annotation]

    return params_dict


def _parse_data(data: Dict[str, Any], params: Dict[str, List[Type]]) -> Any:
    """
    Parse the data from the incoming message.
    :param data: The data from the incoming message
    :param params: The parameters for the on_message decorator
    :raises ValueError: If the data cannot be parsed
    :return: The parsed data
    """

    required_params = list(params.values())[0]
    if inspect._empty in required_params:
        return data

    if not isinstance(data, dict):
        if type(data) in required_params:
            return data
        else:
            raise ValueError(f"Parameter type {type(data)} not found in handlers functions")

    if not len(required_params):
        raise ValueError("One field must be required in handlers functions")

    for class_ in required_params:
        try:
            return class_(**data)
        except (ValidationError, TypeError):
            continue

    raise ValueError(f"Cannot parse data {data} to {required_params}")


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
        Constructor for the Client class, which is used to interact with RabbitMQ, declare queues, and
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
        if self._connection and not self._connection.is_closed:
            _logger.warning("You are trying to connect to RabbitMQ while already connected")

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

        params = _params_dict(function)
        if not len(params.keys()):
            raise ValueError(f"One field must be required in handlers functions: {function.__name__}")

        if len(params.keys()) > 1:
            raise ValueError(f"Only one field must be required in handlers functions: {function.__name__}")

        data = _parse_data(data, params)

        _logger.debug(f"Received message {data} from {message.routing_key}")

        returned = await function(data)

        if function.__annotations__.get("return") is not None:
            return_type = function.__annotations__["return"]
            if hasattr(return_type, '__args__'):
                return_type = return_type.__args__
            
            if not issubclass(type(returned), return_type):
                raise ValueError(f"Function must return a {return_type} or a subclass")

            
        if not is_serializable(returned):
            raise ValueError("Function must return a serializable object")

        if isinstance(returned, BaseModel):
            returned = returned.model_dump_json()

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
        :param instance_id: The instance ID to use
        :param remove: Whether to remove the queues after consuming them
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
