from setuptools import setup, find_packages

setup(
    name='microrabbit',
    version='0.3.1',
    description='A RabbitMQ framework for server utilities',
    author='tonno7103',
    url="https://github.com/TonnoBelloSnello/microrabbit",
    packages=find_packages(),
    install_requires=[
        "aio_pika",
    ]
)
