from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend

from app.config import get_settings

_settings = get_settings()

result_backend = RedisAsyncResultBackend(redis_url=_settings.redis_url)

broker = ListQueueBroker(url=_settings.redis_url).with_result_backend(result_backend)


def _register_middlewares() -> None:
    from app.workers.middlewares import LoggingMiddleware, RetryMiddleware

    broker.add_middlewares(LoggingMiddleware(), RetryMiddleware())


_register_middlewares()


import importlib

importlib.import_module("app.workers.agent_task")


async def startup_broker() -> None:
    await broker.startup()


async def shutdown_broker() -> None:
    await broker.shutdown()
