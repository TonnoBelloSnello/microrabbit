import asyncio
import pytest

from aiormq.exceptions import ChannelLockedResource
from microrabbit import Client
from microrabbit.types import QueueOptions, ConsumerOptions


@pytest.mark.asyncio
async def test_connection(client: Client):
    assert await client.is_connected() is True, "Connection failed"


@pytest.mark.asyncio
async def test_create_queue(client: Client):
    @client.on_message(
        "test_create_queue",
        QueueOptions(exclusive=True, auto_delete=True),
        ConsumerOptions(exclusive=True, no_ack=True)
    )
    async def test(_) -> dict:
        return {"connected": True}

    assert await client.is_connected() is True, "Connection failed"
    task = asyncio.create_task(client.run())
    assert task.done() is False, "Task is done"
    try:
        queue = await client.declare_queue(
            "queue_name",
            QueueOptions(exclusive=True, auto_delete=True)
        )

        queue.consume(lambda _: None, exclusive=True, no_ack=True)
        assert False, "Queue exists"
    except ChannelLockedResource:
        assert True


@pytest.mark.asyncio
async def test_publish(client: Client):
    @client.on_message(
        "test_publish",
        QueueOptions(exclusive=True, auto_delete=True),
        ConsumerOptions(exclusive=True, no_ack=True)
    )
    async def test(_) -> dict:
        return {"connected": True}

    assert await client.is_connected() is True, "Connection failed"
    task = asyncio.create_task(client.run())
    assert task.done() is False, "Task is done"
    try:
        resp = await client.simple_publish("test_publish", {"test": "data"})
        assert resp == "{'connected': True}", "Publish failed"
    except asyncio.TimeoutError:
        assert False, "Timeout"


@pytest.mark.asyncio
async def test_on_ready(client: Client):
    dummy = False

    @client.on_ready
    async def on_ready():
        nonlocal dummy
        dummy = True

    assert await client.is_connected() is True, "Connection failed"
    task = asyncio.create_task(client.run())
    assert task.done() is False, "Task is done"
    await asyncio.sleep(1)
    assert dummy is True, "On ready failed"