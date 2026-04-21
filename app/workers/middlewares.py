from typing import Any

from loguru import logger
from taskiq import TaskiqMessage, TaskiqMiddleware, TaskiqResult


class LoggingMiddleware(TaskiqMiddleware):
    async def pre_execute(self, message: TaskiqMessage) -> TaskiqMessage:
        logger.info("Taskiq task started: {}", message.task_name)
        return message

    async def post_save(self, message: TaskiqMessage, result: TaskiqResult[Any]) -> None:
        if result.error:
            logger.error("Taskiq task failed: {} error={}", message.task_name, result.error)
            return
        logger.info("Taskiq task finished: {}", message.task_name)


class RetryMiddleware(TaskiqMiddleware):
    """Retries are applied in `run_agent_task` with exponential backoff (up to 3 retries)."""

    async def pre_execute(self, message: TaskiqMessage) -> TaskiqMessage:
        message.labels.setdefault("retry_policy", "exponential")
        return message
