"""Flow 运行时行为测试"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from runtime import (
    EventLoop,
    EzRuntimeError,
    FakeIOSource,
    FlowScope,
    Future,
    TaskState,
    TimerSource,
    errCancel,
    errTimeout,
)


def test_timer_sleep_wakes_task_after_virtual_time():
    loop = EventLoop()
    seen = []

    def worker():
        seen.append(("before", loop.now))
        yield loop.sleep(10)
        seen.append(("after", loop.now))
        return "done"

    task = loop.spawn(worker())
    result = loop.run(task)

    assert result == "done"
    assert loop.now == 10
    assert seen == [("before", 0), ("after", 10)]
    assert task.state == TaskState.DONE


def test_scheduler_runs_ready_tasks_while_one_task_sleeps():
    loop = EventLoop()
    order = []

    def slow():
        order.append("slow-before")
        yield loop.sleep(10)
        order.append("slow-after")
        return "slow"

    def fast():
        order.append("fast")
        return "fast"
        yield

    slow_task = loop.spawn(slow())
    fast_task = loop.spawn(fast())

    loop.run()

    assert slow_task.result == "slow"
    assert fast_task.result == "fast"
    assert order == ["slow-before", "fast", "slow-after"]


def test_race_returns_first_completed_result():
    loop = EventLoop()

    def slow():
        yield loop.sleep(20)
        return "slow"

    def fast():
        yield loop.sleep(5)
        return "fast"

    def main():
        result = yield from loop.race([slow, fast])
        return result

    assert loop.run(loop.spawn(main())) == "fast"
    assert loop.now == 5


def test_race_cancels_losers():
    loop = EventLoop()
    sources = []

    def slow():
        source = loop.sleep(20)
        sources.append(source)
        yield source
        return "slow"

    def fast():
        yield loop.sleep(5)
        return "fast"

    def main():
        return (yield from loop.race([slow, fast]))

    assert loop.run(loop.spawn(main())) == "fast"
    assert sources[0].cancelled
    slow_task = next(task for task in loop.tasks if task.parent is not None and task.state == TaskState.CANCELLED)
    assert slow_task.state == TaskState.CANCELLED


def test_race_timeout_raises_err_timeout_and_cancels_all():
    loop = EventLoop()

    def first():
        yield loop.sleep(100)
        return "first"

    def second():
        yield loop.sleep(100)
        return "second"

    def main():
        return (yield from loop.race([first, second], timeout=10))

    task = loop.spawn(main())
    with pytest.raises(EzRuntimeError) as exc:
        loop.run(task)

    assert exc.value.code == errTimeout
    branch_tasks = [t for t in loop.tasks if t.parent is task]
    assert len(branch_tasks) == 2
    assert all(t.state == TaskState.CANCELLED for t in branch_tasks)


def test_cancel_waiting_task_raises_err_cancel():
    loop = EventLoop()
    caught = []

    def worker():
        try:
            yield loop.sleep(50)
        except EzRuntimeError as exc:
            caught.append(exc.code)
            raise

    task = loop.spawn(worker())
    loop.step()
    loop.cancel(task)

    with pytest.raises(EzRuntimeError) as exc:
        loop.run(task)

    assert exc.value.code == errCancel
    assert caught == [errCancel]
    assert task.state == TaskState.CANCELLED


def test_cancel_propagates_to_children():
    loop = EventLoop()

    def child():
        yield loop.sleep(50)
        return "child"

    def parent():
        loop.spawn(child(), parent=loop.current_task)
        yield loop.sleep(100)
        return "parent"

    task = loop.spawn(parent())
    loop.step()
    child_task = task.children[0]
    loop.step()
    child_source = child_task.waiting_source

    loop.cancel(task)

    with pytest.raises(EzRuntimeError):
        loop.run(task)

    assert child_task.state == TaskState.CANCELLED
    assert child_source.cancelled


def test_wait_dependency_resumes_when_producer_done():
    loop = EventLoop()
    order = []

    def producer():
        yield loop.sleep(10)
        order.append("producer")
        return 42

    def consumer(task):
        value = yield from loop.wait(task)
        order.append(("consumer", value))
        return value

    producer_task = loop.spawn(producer())
    consumer_task = loop.spawn(consumer(producer_task))

    assert loop.run(consumer_task) == 42
    assert order == ["producer", ("consumer", 42)]
    assert producer_task.state == TaskState.DONE
    assert consumer_task.state == TaskState.DONE


def test_future_wait_resumes_when_completed():
    loop = EventLoop()
    future = Future()

    def consumer():
        value = yield from loop.wait(future)
        return value + 1

    task = loop.spawn(consumer())
    loop.step()
    future.set_result(41)
    loop.wake_waiters(future)

    assert loop.run(task) == 42


def test_timer_source_cancel_is_idempotent():
    source = TimerSource(10)
    source.cancel()
    source.cancel()

    assert source.cancelled


def test_flow_scope_runs_independent_suspend_points_concurrently():
    loop = EventLoop()

    def main():
        scope = FlowScope(loop)
        scope.spawn_suspend("a", lambda: loop.sleep(20, "a"))
        scope.spawn_suspend("b", lambda: loop.sleep(10, "b"))
        a = yield from scope.get("a")
        b = yield from scope.get("b")
        yield from scope.finish()
        return a + b

    assert loop.run(loop.spawn(main())) == "ab"
    assert loop.now == 20


def test_flow_scope_waits_when_reading_dependency():
    loop = EventLoop()
    order = []

    def main():
        scope = FlowScope(loop)
        scope.spawn_suspend("a", lambda: loop.sleep(20, "a"))
        a = yield from scope.get("a")
        order.append(("a", loop.now))
        scope.spawn_suspend("b", lambda: loop.sleep(10, a + "b"))
        b = yield from scope.get("b")
        return b

    assert loop.run(loop.spawn(main())) == "ab"
    assert order == [("a", 20)]
    assert loop.now == 30


def test_flow_scope_finish_waits_for_side_effects():
    loop = EventLoop()
    done = []

    def side_effect():
        yield loop.sleep(15)
        done.append(loop.now)
        return None

    def main():
        scope = FlowScope(loop)
        scope.spawn_task("write", side_effect())
        yield from scope.finish()
        return "done"

    assert loop.run(loop.spawn(main())) == "done"
    assert done == [15]
    assert loop.now == 15


def test_fake_io_source_wakes_task_with_result():
    loop = EventLoop()

    def worker():
        data = yield FakeIOSource(delay_ms=8, result="data")
        return data

    assert loop.run(loop.spawn(worker())) == "data"
    assert loop.now == 8


def test_cancel_fake_io_source_discards_late_completion():
    loop = EventLoop()

    def worker():
        yield FakeIOSource(delay_ms=8, result="data")
        return "done"

    task = loop.spawn(worker())
    loop.step()
    source = task.waiting_source
    loop.cancel(task)

    with pytest.raises(EzRuntimeError) as exc:
        loop.run(task)

    assert exc.value.code == errCancel
    assert source.cancelled
    loop.now = 8
    loop.step()
    assert task.state == TaskState.CANCELLED


def test_fake_io_source_error_propagates():
    loop = EventLoop()
    error = EzRuntimeError(4, "io")

    def worker():
        yield FakeIOSource(delay_ms=5, error=error)

    task = loop.spawn(worker())
    with pytest.raises(EzRuntimeError) as exc:
        loop.run(task)

    assert exc.value is error
    assert task.state == TaskState.FAILED
