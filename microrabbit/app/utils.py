import importlib.util
import json
from abc import ABCMeta
from pathlib import Path


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class AbstractSingleton(Singleton, ABCMeta):
    pass


class PluginLoader:
    def __init__(self, plugins_dir: Path):
        self.plugins_dir = plugins_dir

    def load_plugins(self):
        for file in self.plugins_dir.iterdir():
            if file.suffix == ".py":
                spec = importlib.util.spec_from_file_location(file.stem, file)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)


def is_serializable(obj):
    try:
        json.dumps(obj)
        return True
    except (TypeError, ValueError):
        return False
