# EzLang Flow 运行时

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from types import GeneratorType
from typing import Any, Callable, Deque, Iterable, Optional

errCancel = 1
errTimeout = 2
errUnsupported = 3
errIO = 4
errNotFound = 5
errPermission = 6


class EzRuntimeError(Exception):
    def __init__(self, code: int, message: str = ""):
        super().__init__(message or f"runtime error {code}")
        self.code = code
        self.message = message or str(self)


class TaskState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING = "waiting"
    DONE = "done"
    CANCELLED = "cancelled"
    FAILED = "failed"


class Future:
    def __init__(self):
        self.done = False
        self.result: Any = None
        self.error: Optional[BaseException] = None
        self.waiters: list[Task] = []

    def set_result(self, result: Any = None):
        if self.done:
            return
        self.done = True
        self.result = result

    def set_error(self, error: BaseException):
        if self.done:
            return
        self.done = True
        self.error = error


class SuspendSource:
    def __init__(self):
        self.loop: Optional[EventLoop] = None
        self.task: Optional[Task] = None
        self.cancelled = False

    def start(self, loop: EventLoop, task: Task):
        self.loop = loop
        self.task = task

    def cancel(self):
        self.cancelled = True


class TimerSource(SuspendSource):
    def __init__(self, delay_ms: int, result: Any = None, error: Optional[BaseException] = None):
        super().__init__()
        self.delay_ms = delay_ms
        self.result = result
        self.error = error
        self.deadline: Optional[int] = None

    def start(self, loop: EventLoop, task: Task):
        super().start(loop, task)
        self.deadline = loop.now + self.delay_ms
        loop.timers.append(self)
        loop.timers.sort(key=lambda item: item.deadline if item.deadline is not None else 0)


class FakeIOSource(TimerSource):
    pass


@dataclass
class Task:
    id: int
    coro: GeneratorType
    parent: Optional[Task] = None
    state: TaskState = TaskState.PENDING
    result: Any = None
    error: Optional[BaseException] = None
    children: list[Task] = field(default_factory=list)
    waiting_source: Optional[SuspendSource] = None
    waiting_future: Optional[Future] = None
    send_value: Any = None
    throw_error: Optional[BaseException] = None
    cancel_requested: bool = False


class FlowScope:
    def __init__(self, loop: EventLoop):
        self.loop = loop
        self.tasks: dict[str, Task] = {}

    def spawn_suspend(self, name: str, source_factory: Callable[[], SuspendSource]) -> Task:
        def runner():
            return (yield source_factory())

        return self.spawn_task(name, runner())

    def spawn_task(self, name: str, coro) -> Task:
        task = self.loop.spawn(coro, parent=self.loop.current_task)
        self.tasks[name] = task
        return task

    def get(self, name: str):
        return (yield from self.loop.wait(self.tasks[name]))

    def finish(self):
        result = None
        for task in self.tasks.values():
            result = yield from self.loop.wait(task)
        return result


class EventLoop:
    def __init__(self):
        self.now = 0
        self.ready: Deque[Task] = deque()
        self.timers: list[TimerSource] = []
        self.tasks: list[Task] = []
        self.current_task: Optional[Task] = None
        self._next_task_id = 1

    def spawn(self, coro, parent: Optional[Task] = None) -> Task:
        if not isinstance(coro, GeneratorType):
            coro = self._value_coro(coro)
        task = Task(self._next_task_id, coro, parent=parent)
        self._next_task_id += 1
        if parent is not None:
            parent.children.append(task)
        self.tasks.append(task)
        self.ready.append(task)
        return task

    def sleep(self, ms: int, result: Any = None) -> TimerSource:
        return TimerSource(ms, result=result)

    def wait(self, target):
        if isinstance(target, Task):
            future = self._task_future(target)
        else:
            future = target
        if future.done:
            if future.error is not None:
                raise future.error
            return future.result
        result = yield future
        return result

    def race(self, branches: Iterable[Callable[[], Any]], timeout: Optional[int] = None):
        owner = self.current_task
        race_future = Future()
        branch_tasks = [self.spawn(branch(), parent=owner) for branch in branches]
        timeout_task = None
        if timeout is not None:
            timeout_task = self.spawn(self._timeout_coro(timeout))
        for task in branch_tasks + ([timeout_task] if timeout_task is not None else []):
            task._future_waiters = getattr(task, "_future_waiters", [])
            task._future_waiters.append(race_future)

        while True:
            for task in branch_tasks:
                if task.state == TaskState.DONE:
                    for other in branch_tasks:
                        if other is not task:
                            self.cancel(other, deliver=False)
                    if timeout_task is not None:
                        self.cancel(timeout_task, deliver=False)
                    return task.result
                if task.state == TaskState.FAILED:
                    for other in branch_tasks:
                        if other is not task:
                            self.cancel(other, deliver=False)
                    if timeout_task is not None:
                        self.cancel(timeout_task, deliver=False)
                    raise task.error
            if timeout_task is not None and timeout_task.state == TaskState.FAILED:
                for task in branch_tasks:
                    self.cancel(task, deliver=False)
                raise timeout_task.error
            try:
                yield race_future
            except EzRuntimeError:
                pass

    def cancel(self, task: Task, *, deliver: bool = True):
        if task.state in {TaskState.DONE, TaskState.CANCELLED, TaskState.FAILED}:
            return
        task.cancel_requested = True
        error = EzRuntimeError(errCancel, "cancelled")
        task.error = error
        if task.waiting_source is not None:
            task.waiting_source.cancel()
            task.waiting_source = None
        if task.waiting_future is not None and task in task.waiting_future.waiters:
            task.waiting_future.waiters.remove(task)
            task.waiting_future = None
        for child in list(task.children):
            self.cancel(child, deliver=False)
        if deliver:
            task.throw_error = error
            if task not in self.ready:
                self.ready.append(task)
        else:
            task.state = TaskState.CANCELLED
            self._wake_task_waiters(task)

    def wake_waiters(self, future: Future):
        for task in list(future.waiters):
            if task.state == TaskState.CANCELLED:
                continue
            task.waiting_future = None
            if future.error is not None:
                task.throw_error = future.error
            else:
                task.send_value = future.result
            self.ready.append(task)
        future.waiters.clear()

    def step(self) -> bool:
        self._wake_due_timers()
        if not self.ready:
            self._advance_to_next_timer()
            self._wake_due_timers()
        if not self.ready:
            return False
        task = self.ready.popleft()
        if task.state in {TaskState.DONE, TaskState.CANCELLED, TaskState.FAILED}:
            return True
        self._resume_task(task)
        return True

    def run(self, task: Optional[Task] = None):
        while True:
            if task is not None and task.state in {TaskState.DONE, TaskState.CANCELLED, TaskState.FAILED}:
                break
            active = self.step()
            if not active:
                break
        if task is None:
            return None
        if task.state == TaskState.DONE:
            return task.result
        if task.error is not None:
            raise task.error
        return task.result

    def _resume_task(self, task: Task):
        self.current_task = task
        task.state = TaskState.RUNNING
        try:
            if task.throw_error is not None:
                error = task.throw_error
                task.throw_error = None
                yielded = task.coro.throw(error)
            else:
                value = task.send_value
                task.send_value = None
                yielded = task.coro.send(value)
        except StopIteration as exc:
            task.state = TaskState.DONE
            task.result = exc.value
            self._wake_task_waiters(task)
        except EzRuntimeError as exc:
            task.error = exc
            task.state = TaskState.CANCELLED if exc.code == errCancel else TaskState.FAILED
            self._wake_task_waiters(task)
        except BaseException as exc:
            task.error = exc
            task.state = TaskState.FAILED
            self._wake_task_waiters(task)
        else:
            self._handle_yield(task, yielded)
        finally:
            self.current_task = None

    def _handle_yield(self, task: Task, yielded):
        if isinstance(yielded, SuspendSource):
            task.state = TaskState.WAITING
            task.waiting_source = yielded
            yielded.start(self, task)
            return
        if isinstance(yielded, Task):
            yielded = self._task_future(yielded)
        if isinstance(yielded, Future):
            if yielded.done:
                if yielded.error is not None:
                    task.throw_error = yielded.error
                else:
                    task.send_value = yielded.result
                self.ready.append(task)
            else:
                task.state = TaskState.WAITING
                task.waiting_future = yielded
                yielded.waiters.append(task)
            return
        task.state = TaskState.PENDING
        task.send_value = yielded
        self.ready.append(task)

    def _wake_due_timers(self):
        due = [timer for timer in self.timers if timer.deadline is not None and timer.deadline <= self.now]
        self.timers = [timer for timer in self.timers if timer not in due]
        for timer in due:
            task = timer.task
            if timer.cancelled or task is None or task.state == TaskState.CANCELLED:
                continue
            task.waiting_source = None
            if timer.error is not None:
                task.throw_error = timer.error
            else:
                task.send_value = timer.result
            self.ready.append(task)

    def _advance_to_next_timer(self):
        active = [timer for timer in self.timers if not timer.cancelled and timer.deadline is not None]
        if active:
            self.now = min(timer.deadline for timer in active)

    def _task_future(self, task: Task) -> Future:
        future = Future()
        if task.state == TaskState.DONE:
            future.set_result(task.result)
        elif task.state in {TaskState.CANCELLED, TaskState.FAILED}:
            future.set_error(task.error or EzRuntimeError(errCancel, "cancelled"))
        else:
            if not hasattr(task, "_future_waiters"):
                task._future_waiters = []
            task._future_waiters.append(future)
        return future

    def _wake_task_waiters(self, task: Task):
        for future in getattr(task, "_future_waiters", []):
            if task.state == TaskState.DONE:
                future.set_result(task.result)
            else:
                future.set_error(task.error or EzRuntimeError(errCancel, "cancelled"))
            self.wake_waiters(future)
        task._future_waiters = []

    def _timeout_coro(self, timeout: int):
        yield self.sleep(timeout)
        raise EzRuntimeError(errTimeout, "timeout")

    @staticmethod
    def _value_coro(value):
        if False:
            yield None
        return value
