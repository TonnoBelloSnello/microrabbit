from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Union


@dataclass
class QueueOptions:
    """
    Queue options for the RabbitMQ queue
    """
    durable: bool = False
    auto_delete: bool = False
    exclusive: bool = False
    arguments: dict[str, Union[bool, bytes, bytearray, Decimal, list, float, int, None, str, datetime]] = None
    timeout: Union[int, float, None] = None
    passive: bool = False

    def to_dict(self) -> dict:
        return {
            "durable": self.durable,
            "auto_delete": self.auto_delete,
            "exclusive": self.exclusive,
            "arguments": self.arguments,
            "timeout": self.timeout,
            "passive": self.passive
        }


@dataclass
class ConsumerOptions:
    """
    Consumer options for the RabbitMQ consumer
    """
    no_ack: bool = False
    exclusive: bool = False
    arguments: dict[str, Union[bool, bytes, bytearray, Decimal, list, float, int, None, str, datetime]] = None
    consumer_tag: str = None
    timeout: Union[int, float, None] = None

    def to_dict(self) -> dict:
        return {
            "no_ack": self.no_ack,
            "exclusive": self.exclusive,
            "arguments": self.arguments,
            "consumer_tag": self.consumer_tag,
            "timeout": self.timeout
        }
