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

    
@pytest.mark.asyncio
async def test_model_return(client: Client):

    class TestCreateQueue(BaseModel):
        name: str
        age: int

    @client.on_message(
        "test_model_return",
        queue_options=QueueOptions(exclusive=True, auto_delete=True),
        consume_options=ConsumerOptions(exclusive=True, no_ack=True)
    )
    async def test(data: Union[int, TestCreateQueue]) -> Union[TestCreateQueue, str]:
        if isinstance(data, TestCreateQueue):
            return data
        
        return -1

    assert await client.is_connected() is True, "Connection failed"
    task = asyncio.create_task(client.run())
    assert task.done() is False, "Task is done"
    result = await client.simple_publish("test_model_return", {"name": "foo", "age": 20})
    assert result == TestCreateQueue(name="foo", age=20).model_dump_json(), "Model failed"


@pytest.mark.asyncio
async def test_model_return_invalid_data(client: Client):

    class TestCreateQueue(BaseModel):
        name: str
        age: int

    try:
        @client.on_message(
            "test_model_return",
            queue_options=QueueOptions(exclusive=True, auto_delete=True),
            consume_options=ConsumerOptions(exclusive=True, no_ack=True)
        )
        async def test(data: Union[int, TestCreateQueue]) -> TestCreateQueue:
            if isinstance(data, TestCreateQueue):
                return data
            
            return -1

        assert await client.is_connected() is True, "Connection failed"
        task = asyncio.create_task(client.run())
        assert task.done() is False, "Task is done"
        await client.simple_publish("test_model_return", 12345, timeout=2)
    except TimeoutError:
        assert True
        return
    
    assert False