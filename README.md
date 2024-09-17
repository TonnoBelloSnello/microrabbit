# MicroRabbit

[![Python 3.8 test](https://github.com/TonnoBelloSnello/microrabbit/actions/workflows/test-3_8.yml/badge.svg)](https://github.com/TonnoBelloSnello/microrabbit/actions/workflows/test-3_8.yml) 
[![Downloads](https://static.pepy.tech/badge/microrabbit)](https://pepy.tech/project/microrabbit)

MicroRabbit is a lightweight, asynchronous Python framework for working with RabbitMQ. It simplifies the process of
setting up RabbitMQ consumers and publishers, making it easy to build microservices and distributed systems.

## Features

- Asynchronous message handling using `asyncio`
- Simple decorator-based message routing
- Plugin system for modular code organization
- Easy-to-use client configuration
- Built-in logging support

## Installation

```bash
pip install microrabbit
```

## Quick Start

Here's a simple example of how to use MicroRabbit:

```python
import asyncio
import logging

from microrabbit import Client
from microrabbit.types import QueueOptions, ConsumerOptions, ConnectionOptions

client = Client(
    host="amqp://guest:guest@localhost/",
    plugins="./plugins",
    connection_type="ROBUST",
    connection_options=ConnectionOptions()
)

log = logging.getLogger(__file__)
logging.basicConfig(level=logging.INFO)


@Client.on_message("queue_name")
async def test(data: dict) -> dict:
    log.info(f"Received message {data}")
    return {"connected": True}


@Client.on_message("queue_name2", queue_options=QueueOptions(exclusive=True), consume_options=ConsumerOptions(no_ack=True))
async def test2(data: dict) -> dict:
    log.info(f"Received message {data}")
    return {"connected": True}


@client.on_ready
async def on_ready():
    log.info("[*] Waiting for messages. To exit press CTRL+C")
    result = await client.simple_publish("queue_name2", {"test": "data"}, timeout=2, decode=True)
    log.info(result)


if __name__ == "__main__":
    asyncio.run(client.run())

```

## Usage

### Client Configuration

Create a `Client` instance with the following parameters:

- `host`: RabbitMQ server URL
- `instance_id`: Unique identifier for the client if not provided it will be generated automatically (optional)
- `plugins`: Path to the plugins folder (optional)
- `connection_type`: Connection type `str (NORMAL, ROBUST)` or `CONNECTION_TYPE`(optional)
- `connection_options`: Connection options `ConnectionOptions` (optional)

```python
from microrabbit import Client
from microrabbit.types import CONNECTION_TYPE, ConnectionOptions

client = Client(
    host="amqp://guest:guest@localhost/",
    instance_id="unique_id",
    plugins="./plugins",
    connection_type=CONNECTION_TYPE.NORMAL,
    connection_options=ConnectionOptions(ssl=True)
)

```

### Message Handling

Use the `@Client.on_message` decorator to define a message handler. The decorator takes the queue name as an argument.
Arguments:
- `queue_name`: Name of the queue
- `instance_id`: Unique identifier for the client if not provided it will be setted as global, 
when a client runs the queue will be consumed (optional)
- `queue_options`: Queue options `QueueOptions` (optional)
- `consume_options`: Consumer options `ConsumerOptions` (optional)
```python
from microrabbit import Client
from microrabbit.types import QueueOptions

@Client.on_message("queue_name", queue_options=QueueOptions(exclusive=True))
async def handler(data: dict):
    # Process the message
    return response_data  # Serializeable data

```

### Ready Event

Use the `@client.on_ready` decorator to define a function that runs when the client is ready:

```python
from microrabbit import Client

client = Client(
    host="amqp://guest:guest@localhost/",
    plugins="./plugins"
)


@client.on_ready
async def on_ready():
    print("Client is ready")

```

### Running the Client

Run the client using `asyncio.run(client.run())`:

```python
import asyncio
from microrabbit import Client

client = Client(
    host="amqp://guest:guest@localhost/",
    plugins="./plugins"
)

if __name__ == "__main__":
    asyncio.run(client.run())

```

### Publishing Messages

Use the `simple_publish` method to publish a message to a queue:

```python
result = await client.simple_publish("queue_name", {"test": "data"}, timeout=2, decode=True)
```

### Running with context manager

```python
import asyncio
from microrabbit import Client

client = Client(
    host="amqp://guest:guest@localhost/",
    plugins="./plugins"
)

async def main():
    async with client:
        await client.run()
        
if __name__ == "__main__":
    asyncio.run(main())

```

## Plugins

MicroRabbit supports a plugin system.
Place your plugin files in the specified plugins folder, and they will be automatically
loaded by the client.

### Plugin Example

```python
# ./plugins/test_plugin.py
from microrabbit import Client


@Client.on_message("test_queue")
async def test_handler(data: dict):
    print(f"Received message: {data}")
    return {"status": "ok"}

```

## Advanced Usage

### Queue Options

Use the `QueueOptions` class to specify queue options:

```python
from microrabbit.types import QueueOptions


@Client.on_message("queue_name", queue_options=QueueOptions(exclusive=True))
async def handler(data: dict):
    # Process the message
    return response_data

```

### Consumer Options

Use the `ConsumerOptions` class to specify consumer options:

```python
from microrabbit.types import ConsumerOptions


@Client.on_message("queue_name", consume_options=ConsumerOptions(no_ack=True))
async def handler(data: dict):
    # Process the message
    return response_data

```

## Contributing

Contributions are welcome! For feature requests, bug reports, or questions, please open an issue.
If you would like to contribute code, please submit a pull request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
