"""短暂的数据库占用结束后，已提交任务仍会被执行一次"""
import sqlite3
from unittest.mock import Mock

import pytest

from lessonweave import jobs, server


def test_worker_recovers_from_a_busy_database_without_losing_the_job(monkeypatch):
    store = Mock()
    job = {'id': 'queued-job'}
    store.claim.side_effect = [sqlite3.OperationalError('database is locked'), job, StopIteration]
    execute = Mock(return_value={'completed': True})
    monkeypatch.setattr(jobs, 'execute', execute)
    monkeypatch.setattr(server.time, 'sleep', lambda seconds: None)
    with pytest.raises(StopIteration):
        server.worker(store)
    execute.assert_called_once_with(store, job)
    store.finish.assert_called_once_with('queued-job', {'completed': True})
