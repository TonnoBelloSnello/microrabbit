import asyncio

import pytest
from aiormq import ChannelAccessRefused
from aiormq.exceptions import ChannelLockedResource

from microrabbit import Client
from microrabbit.types import QueueOptions, ConsumerOptions


@pytest.mark.asyncio
async def test_connection(client: Client):
    is_connected = await client.is_connected()
    await client.close()
    assert is_connected is True, "Connection failed"


@pytest.mark.asyncio
async def test_create_queue(client: Client):
    @client.on_message(
        "test_create_queue",
        queue_options=QueueOptions(exclusive=True, auto_delete=True),
        consume_options=ConsumerOptions(exclusive=True, no_ack=True)
    )
    async def test(_) -> dict:
        return {"connected": True}

    assert await client.is_connected() is True, "Connection failed"
    task = asyncio.create_task(client.run())
    assert task.done() is False, "Task is done"
    try:
        await asyncio.sleep(1)
        queue = await client.declare_queue(
            "test_create_queue",
            QueueOptions(exclusive=True, auto_delete=True)
        )

        async def T():
            return None

        await queue.consume(T, exclusive=True, no_ack=True)
        assert False, "Queue exists"
    except (ChannelLockedResource, ChannelAccessRefused):
        assert True
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_publish(client: Client):
    @client.on_message(
        "test_publish",
        queue_options=QueueOptions(exclusive=True, auto_delete=True),
        consume_options=ConsumerOptions(exclusive=True, no_ack=True)
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
    finally:
        await client.close()


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
    await client.close()
    assert dummy is True, "On ready failed"


@pytest.mark.asyncio
async def test_not_instance_id(client: Client):
    assert await client.is_connected() is True, "Connection failed"

    @client.on_message(
        "test_instance_id",
        queue_options=QueueOptions(exclusive=True, auto_delete=True),
        instance_id="instance_id"
    )
    async def test(_) -> dict:
        return {"connected": True}

    task = asyncio.create_task(client.run())
    assert task.done() is False, "Task is done"
    try:
        await asyncio.sleep(1)
        queue = await client.declare_queue(
            "test_instance_id",
            QueueOptions(exclusive=True, auto_delete=True)
        )

        async def T():
            return None

        await queue.consume(T, exclusive=True, no_ack=True)
        assert True, "Queue exists"
    except (ChannelLockedResource, ChannelAccessRefused):
        assert False
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_instance_id(client: Client):
    @client.on_message(
        "test_instance_id",
        queue_options=QueueOptions(exclusive=True, auto_delete=True),
        instance_id=client.instance_id
    )
    async def test(_) -> dict:
        return {"connected": True}

    assert await client.is_connected() is True, "Connection failed"
    task = asyncio.create_task(client.run())
    assert task.done() is False, "Task is done"
    try:
        await asyncio.sleep(1)
        queue = await client.declare_queue(
            "test_instance_id",
            QueueOptions(exclusive=True, auto_delete=True)
        )

        async def T():
            return None

        await queue.consume(T, exclusive=True, no_ack=True)
        assert False, "Queue does not exists"
    except (ChannelLockedResource, ChannelAccessRefused):
        assert True
    finally:
        await client.close()
