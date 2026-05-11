from __future__ import annotations

import asyncio

from web.services.agent_runner import Job, JobStatus


def make_job() -> Job:
    return Job(job_id="test-id", filename="test.pdf", file_path="/tmp/test.pdf")  # noqa: S108


def test_job_initial_state():
    job = make_job()
    assert job.status == JobStatus.PENDING
    assert job.events == []
    assert job.result is None
    assert job.error is None


def test_push_appends_event():
    job = make_job()
    job.push({"type": "status", "message": "hello"})
    assert len(job.events) == 1
    assert job.events[0]["message"] == "hello"


async def test_push_wakes_waiter():
    job = make_job()

    async def _pusher():
        await asyncio.sleep(0.05)
        job.push({"type": "status", "message": "ping"})

    task = asyncio.create_task(_pusher())
    cursor = await asyncio.wait_for(job.wait_for_events(0, timeout=2.0), timeout=3.0)
    await task
    assert cursor == 0  # wait_for_events returns last cursor, new events available
    assert len(job.events) == 1


async def test_push_does_not_block_on_no_waiter():
    job = make_job()
    for i in range(10):
        job.push({"type": "status", "message": str(i)})
    assert len(job.events) == 10


async def test_wait_for_events_returns_immediately_when_events_exist():
    job = make_job()
    job.push({"type": "status", "message": "already here"})
    cursor = await asyncio.wait_for(job.wait_for_events(0, timeout=0.1), timeout=1.0)
    assert cursor == 0


async def test_wait_for_events_times_out_gracefully():
    job = make_job()
    cursor = await asyncio.wait_for(job.wait_for_events(0, timeout=0.1), timeout=1.0)
    assert cursor == 0  # no events pushed, returns same cursor after timeout
