def get_loglevel(logger) -> int:
    handlers = logger._core.handlers  # Private API

    if not handlers:
        raise RuntimeError("Logger has no configured sinks")

    latest_handler_id = max(handlers)
    return handlers[latest_handler_id].levelno
