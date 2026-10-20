"""检查只登记待修问题，调度器继续处理现有材料和产物"""
import time
from pathlib import Path
from .storage import read, save, WRITE_LOCK

BEHAVIORS = ('decompose', 'generate', 'check', 'repair')


def record(root, task, messages, behavior='check'):
    if isinstance(messages, str):
        messages = [messages]
    with WRITE_LOCK:
        path = Path(root) / 'runtime/findings.json'
        rows = read(path, {'behaviors': list(BEHAVIORS), 'items': []})
        for message in messages:
            if not any(r['task'] == task and r['message'] == message for r in rows['items']):
                rows['items'].append({'task': task, 'behavior': behavior, 'message': message,
                                      'status': 'recorded', 'recorded_at': time.time()})
        save(path, rows)
    return messages
