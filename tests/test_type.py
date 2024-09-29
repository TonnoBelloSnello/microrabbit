import asyncio

import pytest

from microrabbit import Client
from microrabbit.types import QueueOptions, ConsumerOptions

from typing import Union
from pydantic import BaseModel

@pytest.mark.asyncio
async def test_model(client: Client):

    class TestCreateQueue(BaseModel):
        name: str
        age: int

    @client.on_message(
        "test_model",
        queue_options=QueueOptions(exclusive=True, auto_delete=True),
        consume_options=ConsumerOptions(exclusive=True, no_ack=True)
    )
    async def test(data: Union[int, TestCreateQueue]) -> dict:
        if isinstance(data, TestCreateQueue):
            return {"status": True}
        
        return {"status": False}

    assert await client.is_connected() is True, "Connection failed"
    task = asyncio.create_task(client.run())
    assert task.done() is False, "Task is done"
    result = await client.simple_publish("test_model", {"name": "foo", "age": 20})
    assert result == "{'status': True}", "Model failed"

    

