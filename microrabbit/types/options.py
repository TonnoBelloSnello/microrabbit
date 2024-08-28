from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal
from typing import Union, Dict, List


@dataclass
class QueueOptions:
    """
    Queue options for the RabbitMQ queue
    """
    durable: bool = False
    auto_delete: bool = False
    exclusive: bool = False
    arguments: Dict[str, Union[bool, bytes, bytearray, Decimal, List, float, int, None, str, datetime]] = None
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
    arguments: Dict[str, Union[bool, bytes, bytearray, Decimal, List, float, int, None, str, datetime]] = None
    consumer_tag: str = None
    timeout: Union[int, float, None] = None

    def to_dict(self) -> dict:
        return asdict(self)
