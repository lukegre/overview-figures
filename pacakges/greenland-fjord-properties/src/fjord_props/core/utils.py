import functools
import warnings
from typing import Callable


def ignore_warnings(category: type[Warning]):
    def ignore_warnings_decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=category)
                return func(*args, **kwargs)

        return wrapper

    return ignore_warnings_decorator
