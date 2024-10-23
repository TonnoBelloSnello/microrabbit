import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal
from ssl import SSLContext
from typing import Union, Dict, List

from aio_pika.abc import SSLOptions, TimeoutType


@dataclass
class QueueOptions:
    """
    Queue options for the RabbitMQ queue
    """
    durable: bool = False
    auto_delete: bool = False
    exclusive: bool = False
    arguments: Dict[str, Union[bool, bytes, bytearray, Decimal, List, float, int, None, str, datetime]]|None = None
    timeout: Union[int, float, None] = None
    passive: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ConsumerOptions:
    """
    Consumer options for the RabbitMQ consumer
    """
    no_ack: bool = False
    exclusive: bool = False
    arguments: Dict[str, Union[bool, bytes, bytearray, Decimal, List, float, int, None, str, datetime]]|None = None
    consumer_tag: str|None = None
    timeout: Union[int, float, None] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ConnectionOptions:
    """
    Connection options for the RabbitMQ connection
    """
    ssl: bool = False
    loop: asyncio.AbstractEventLoop|None = None
    ssl_options: SSLOptions|None = None
    ssl_context: SSLContext|None = None
    timeout: TimeoutType = None
    client_properties: Dict[str, Union[bool, bytes, bytearray, Decimal, List, float, int, None, str, datetime]]|None = None

    def to_dict(self) -> dict:
        return {
            "ssl": self.ssl,
            "loop": self.loop,
            "ssl_options": self.ssl_options,
            "ssl_context": self.ssl_context,
            "timeout": self.timeout,
            "client_properties": self.client_properties
        }
