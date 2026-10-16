"""
ALPHA Quant — Phase 6: Background Task Queue & Worker.
Manages asynchronous execution for long-running backtests and compute-intensive quantitative jobs.
"""

import asyncio
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional
import uuid

from app.core.logging import get_logger

logger = get_logger("orchestration.tasks")


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TaskRecord:
    def __init__(self, task_id: str, task_type: str, metadata: Optional[Dict[str, Any]] = None):
        self.task_id = task_id
        self.task_type = task_type
        self.status = TaskStatus.PENDING
        self.progress = 0.0
        self.result: Optional[Dict[str, Any]] = None
        self.error: Optional[str] = None
        self.metadata = metadata or {}
        self.created_at = datetime.now(timezone.utc)
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status.value,
            "progress": round(self.progress, 2),
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "message": f"Task is {self.status.value.lower()}",
        }


class BackgroundTaskManager:
    """
    In-memory background task queue and execution supervisor.
    """
    def __init__(self):
        self._tasks: Dict[str, TaskRecord] = {}
        self._asyncio_tasks: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    def enqueue_task(
        self,
        task_type: str,
        coro_fn: Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> TaskRecord:
        """
        Registers and schedules a coroutine for asynchronous execution in background.
        """
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        record = TaskRecord(task_id=task_id, task_type=task_type, metadata=metadata)
        self._tasks[task_id] = record

        async def _runner():
            record.status = TaskStatus.RUNNING
            record.started_at = datetime.now(timezone.utc)
            record.progress = 0.1
            logger.info("background_task_started", task_id=task_id, task_type=task_type)
            try:
                result = await coro_fn(*args, **kwargs)
                record.result = result
                record.progress = 1.0
                record.status = TaskStatus.COMPLETED
                record.completed_at = datetime.now(timezone.utc)
                logger.info("background_task_completed", task_id=task_id, task_type=task_type)
            except asyncio.CancelledError:
                record.status = TaskStatus.CANCELLED
                record.completed_at = datetime.now(timezone.utc)
                logger.warning("background_task_cancelled", task_id=task_id)
            except Exception as exc:
                record.error = str(exc)
                record.status = TaskStatus.FAILED
                record.completed_at = datetime.now(timezone.utc)
                logger.error("background_task_failed", task_id=task_id, error=str(exc))
            finally:
                self._asyncio_tasks.pop(task_id, None)

        async_task = asyncio.create_task(_runner())
        self._asyncio_tasks[task_id] = async_task
        return record

    def get_task(self, task_id: str) -> Optional[TaskRecord]:
        return self._tasks.get(task_id)

    def list_tasks(self, task_type: Optional[str] = None) -> List[TaskRecord]:
        if task_type:
            return [t for t in self._tasks.values() if t.task_type == task_type]
        return list(self._tasks.values())


# Global singleton
_task_manager_instance: Optional[BackgroundTaskManager] = None


def get_task_manager() -> BackgroundTaskManager:
    global _task_manager_instance
    if _task_manager_instance is None:
        _task_manager_instance = BackgroundTaskManager()
    return _task_manager_instance
