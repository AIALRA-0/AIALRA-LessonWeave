"""向已登录用户展示运行资源和生效配置，不返回账号、凭据或服务器路径"""
import os
import platform
import shutil
import time
from importlib.metadata import PackageNotFoundError,version
from pathlib import Path
from .concurrency import options


def snapshot(data_root):
    memory={}
    if Path('/proc/meminfo').is_file():
        values={line.split(':')[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if len(line.split())>=2 and line.split()[1].isdigit()}
        memory={'total_bytes':values.get('MemTotal'),'available_bytes':values.get('MemAvailable')}
    elif os.name=='nt':
        import ctypes
        class Memory(ctypes.Structure):
            _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(key,ctypes.c_ulonglong) for key in ['total','available','page_total','page_available','virtual_total','virtual_available','extended']]
        value=Memory();value.length=ctypes.sizeof(value)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value)):
            memory={'total_bytes':value.total,'available_bytes':value.available}
    packages={}
    for name in ['docling','PyMuPDF','tree-sitter-language-pack','playwright']:
        try:packages[name]=version(name)
        except PackageNotFoundError:packages[name]=None
    disk=shutil.disk_usage(data_root)
    return {'observed_at':time.time(),'workflow':'lean-c-1.0','platform':platform.system(),'python':platform.python_version(),
        'cpu_count':os.cpu_count(),'load_average':list(os.getloadavg()) if hasattr(os,'getloadavg') else None,
        'memory':memory,'disk':{'total_bytes':disk.total,'free_bytes':disk.free},'profile':options(),
        'models':{'writing':{'model':os.environ.get('LESSONWEAVE_MODEL','gpt-6.1-sol'),'effort':os.environ.get('LESSONWEAVE_EFFORT','high')},
                  'translation':{'model':'deepseek-flash','effort':'off'}},
        'capabilities':{'codex':bool(os.environ.get('LESSONWEAVE_CODEX') or shutil.which('codex')),
            'flash':bool(os.environ.get('AIALRA_DEEPSEEK_OFFICIAL_KEY') or os.environ.get('LESSONWEAVE_DEEPSEEK_KEY')),
            'browser_archive':bool(shutil.which('docker') or os.environ.get('LESSONWEAVE_ARCHIVE_SSH'))},
        'parsers':packages,'project_scheduling':'项目按提交顺序执行，每个项目内部按已配置额度并行'}
