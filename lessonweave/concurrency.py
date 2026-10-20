"""按实测配置共享调用额度，翻译使用独立额度，项目现有环境覆盖继续有效"""
import json
import os
from pathlib import Path
import threading
from contextlib import contextmanager

DEFAULTS = {'writing_calls':144,'translation_calls':12,'translation_bytes':24000,
            'bridge_calls':7,'bridge_batch_sections':16,'repair_calls':3}
ENV = {'writing_calls':'LESSONWEAVE_WRITING_CALLS','translation_calls':'LESSONWEAVE_TRANSLATION_CALLS',
       'translation_bytes':'LESSONWEAVE_TRANSLATION_BYTES','bridge_calls':'LESSONWEAVE_BRIDGE_CALLS',
       'bridge_batch_sections':'LESSONWEAVE_BRIDGE_BATCH_SECTIONS','repair_calls':'LESSONWEAVE_REPAIR_CALLS'}
_lock = threading.Lock()
_slots = {}


def options():
    path = Path(os.environ.get('LESSONWEAVE_RUNTIME_PROFILE', Path(__file__).resolve().parents[1] / 'framework/05_writing/runtime-profile.json'))
    result = dict(DEFAULTS)
    if path.is_file():
        result.update({key: value for key, value in json.loads(path.read_text('utf8')).items() if key in DEFAULTS})
    for key, variable in ENV.items():
        if variable in os.environ:
            result[key] = os.environ[variable]if isinstance(DEFAULTS[key],str)else int(os.environ[variable])
    result['sol_calls'] = int(os.environ.get('LESSONWEAVE_CALLS', max(result[key]for key in ['writing_calls','bridge_calls','repair_calls'])))
    return result


def provider_slots(provider):
    config = options()
    count = config['translation_calls'] if provider == 'deepseek-official' else config['sol_calls']
    key = provider, count
    with _lock:
        if key not in _slots:
            _slots[key] = threading.BoundedSemaphore(count)
        return _slots[key]


@contextmanager
def call_slots(provider, role):
    config=options()
    group=None
    if provider!='deepseek-official':
        if role=='lean_writing':group='writing_calls'
        elif role=='lean_bridge':group='bridge_calls'
        elif role=='lean_repair':group='repair_calls'
    if group:
        key='role',group,config[group]
        with _lock:
            if key not in _slots:_slots[key]=threading.BoundedSemaphore(config[group])
            stage_slots=_slots[key]
        with stage_slots,provider_slots(provider):yield
    else:
        with provider_slots(provider):yield
