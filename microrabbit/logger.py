import logging

logger: logging.Logger = logging.getLogger("microrabbit")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the given name. If the name is the same as the package name, the package name is removed from the
    logger name.
    :param name: The name of the logger

    :return: The logger with the given name
    """

    splitted = name.split(".", 1)
    if len(splitted) == 1:
        package = splitted[0]
        module = ""
    else:
        package, module = splitted

    if package == logger.name:
        name = module
    return logger.getChild(name)
