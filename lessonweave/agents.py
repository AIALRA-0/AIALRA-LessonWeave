"""每项语义任务使用独立上下文，按实际请求复用结果并保留用量"""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import threading
import time
import urllib.request
import importlib

import jsonschema
from .storage import read, save

SLOTS = threading.BoundedSemaphore(int(os.environ.get('LESSONWEAVE_CALLS', '3')))
ADAPTERS = {}


class AgentCallFailure(RuntimeError):
    def __init__(self,kind,message):
        super().__init__(message)
        self.kind=kind


def event_failure(events):
    messages=[]
    for event in events:
        if event.get('type') in {'error','turn.failed'}:
            messages.append(str(event.get('message') or event.get('error',{}).get('message','')))
    if any('max_output_tokens' in message for message in messages):
        return 'output_limit'
    return 'execution_failed'


def codex_executable():
    if os.environ.get('LESSONWEAVE_CODEX'):
        return os.environ['LESSONWEAVE_CODEX']
    bundled = list((Path(os.environ.get('LOCALAPPDATA', ''))/'OpenAI/Codex/bin').glob('*/codex.exe')) if os.name=='nt' else []
    return str(max(bundled,key=lambda path:path.stat().st_mtime)) if bundled else shutil.which('codex')


def register_backend(name, adapter):
    ADAPTERS[name] = adapter


def wire_schema(node):
    if isinstance(node, dict):
        return {key: wire_schema(value) for key, value in node.items() if key != 'uniqueItems'}
    if isinstance(node, list):
        return [wire_schema(value) for value in node]
    return node


class CodexAdapter:
    capabilities = {'images': True, 'schema': True, 'independent_context': True}

    def execute(self, task, folder):
        executable = codex_executable()
        if not executable:
            raise RuntimeError('执行环境尚未找到 Codex CLI')
        save(folder / 'wire-schema.json', wire_schema(task['schema']))
        cold = folder / 'context'
        cold.mkdir(exist_ok=True)
        args = [executable, 'exec', '--ignore-user-config', '--skip-git-repo-check', '--ephemeral',
                '-C', str(cold), '-s', 'read-only', '-m', task['model'], '-c', 'model_reasoning_effort="' + task['effort'] + '"',
                '-c', 'project_doc_max_bytes=0', '-c', 'features.shell_tool=false', '-c', 'features.multi_agent=false', '--json', '--output-schema', str(folder / 'wire-schema.json'),
                '-o', str(folder / 'response.json')]
        for image in task['images']:
            args.extend(['-i', str(image)])
        args.append('-')
        env = dict(os.environ, PYTHONIOENCODING='utf-8')
        for key in list(env):
            if key in {'OPENAI_API_KEY', 'CODEX_API_KEY','LESSONWEAVE_API_KEY','LESSONWEAVE_TRILIUM_TOKEN'} or any(part in key for part in ('KUAFUSHE', 'DEEPSEEK', 'GITHUB_TOKEN', 'GH_TOKEN')):
                env.pop(key)
        with (folder / 'events.jsonl').open('w', encoding='utf-8') as events, (folder / 'stderr.txt').open('w', encoding='utf-8') as errors:
            process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=events, stderr=errors,
                                       text=True, encoding='utf-8', env=env)
            save(folder / 'process.json', {'pid': process.pid, 'started': time.time()})
            try:
                process.communicate(task['prompt'], timeout=int(os.environ.get('LESSONWEAVE_TIMEOUT', '1800')))
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
                save(folder/'receipt.json',{'exit_code':process.returncode,'failure_kind':'timeout','usage':[],'usage_measurement':'unavailable'})
                raise AgentCallFailure('timeout','Codex 已达到任务期限，已保留完成的阶段和本次调用记录')
        parsed = []
        for line in (folder / 'events.jsonl').read_text('utf-8').splitlines():
            try:
                parsed.append(json.loads(line))
            except ValueError:
                continue
        receipts = [event.get('usage', {}) for event in parsed if event.get('type') == 'turn.completed']
        record = {'exit_code': process.returncode, 'session_id': next((e.get('thread_id') for e in parsed if e.get('type') == 'thread.started'), None),
                  'usage': receipts, 'parent_conversation_inherited': False, 'resume_or_fork': False,
                  'tool_calls': [e.get('item', {}).get('type') for e in parsed if e.get('type') == 'item.started' and e.get('item', {}).get('type') in {'command_execution', 'mcp_tool_call'}]}
        if process.returncode or not (folder/'response.json').is_file():
            record.update(failure_kind=event_failure(parsed),usage_measurement='reported' if receipts else 'unavailable')
        save(folder / 'receipt.json', record)
        if process.returncode or not (folder / 'response.json').is_file():
            message='本次清点或生成超过模型输出上限，需要缩小任务后继续，已完成结果保留' if record['failure_kind']=='output_limit' else 'Codex 调用没有完成，原始退出状态已保存'
            raise AgentCallFailure(record['failure_kind'],message)
        return read(folder / 'response.json'), record


class OpenAICompatibleAdapter:
    capabilities = {'images': True, 'schema': True, 'independent_context': True}

    def execute(self, task, folder):
        endpoint = os.environ.get('LESSONWEAVE_API_BASE', '').rstrip('/')
        key = os.environ.get('LESSONWEAVE_API_KEY')
        if not endpoint.startswith('https://') or not key:
            raise ValueError('第三方后端需要配置 HTTPS 接口和服务端密钥')
        content = [{'type': 'text', 'text': task['prompt']}]
        if task['images']:
            import base64
            import mimetypes
            for path in task['images']:
                mime = mimetypes.guess_type(path)[0] or 'image/png'
                content.append({'type': 'image_url', 'image_url': {'url': 'data:' + mime + ';base64,' + base64.b64encode(Path(path).read_bytes()).decode()}})
        body = {'model': task['model'], 'messages': [{'role': 'user', 'content': content}],
                'reasoning_effort': task['effort'],
                'response_format': {'type': 'json_schema', 'json_schema': {'name': 'lessonweave_task', 'strict': True, 'schema': wire_schema(task['schema'])}}}
        request = urllib.request.Request(endpoint + '/chat/completions', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
        with urllib.request.urlopen(request, timeout=1800) as response:
            result = json.load(response)
        save(folder / 'api-response.json', result)
        value = json.loads(result['choices'][0]['message']['content'])
        save(folder / 'response.json', value)
        return value, {'usage': [result.get('usage', {})], 'response_id': result.get('id'), 'exit_code': 0, 'parent_conversation_inherited': False, 'resume_or_fork': False}


register_backend('codex', CodexAdapter)
register_backend('openai-compatible', OpenAICompatibleAdapter)


class Backend:
    def __init__(self, root, provider=None, role='generation'):
        self.root = Path(root).resolve()
        self.role = role
        self.provider = os.environ.get('LESSONWEAVE_BACKEND', 'codex')
        if os.environ.get('LESSONWEAVE_ADAPTER_MODULE'):
            importlib.import_module(os.environ['LESSONWEAVE_ADAPTER_MODULE'])
        if self.provider not in ADAPTERS:
            raise ValueError('当前后端尚未登记适配器：'+self.provider)
        self.model = os.environ.get('LESSONWEAVE_MODEL', 'gpt-6.1-sol')
        self.effort = os.environ.get('LESSONWEAVE_EFFORT', 'high')

    def call(self, name, prompt, schema, images=None, round_number=0):
        # 写作与审查只复用字节一致的输入，材料变化或反馈变化会建立新请求
        from .legacy import author_format, remove_empty_extras
        state = read(self.root / 'runtime/state.json', {})
        feedback = state.get('feedback', {}).get(name)
        if feedback:
            prompt += '\n根据这一轮集中反馈修正当前任务，保留未受影响的事实和映射\n' + json.dumps(feedback, ensure_ascii=False)
        common = '\n'.join(__import__('book_generation').RULES)
        objective=read(self.root/'00_source/input.json',{}).get('system_prompt')
        if objective:
            common+='\n用户的学习目标：'+objective+'\n本次只执行当前任务规定的角色与输出合同'
        task = {'prompt': common + '\n只读取本次提供的材料，不使用工具，只返回约定 JSON\n\n' + prompt,
                'schema': schema, 'images': list(dict.fromkeys(str((Path(p) if Path(p).is_absolute() else self.root/Path(p)).resolve()) for p in images or [])),
                'model': self.model, 'effort': self.effort, 'role': self.role, 'backend': self.provider}
        identity = dict(task, executor=codex_executable() if self.provider=='codex' else os.environ.get('LESSONWEAVE_API_BASE'), images=[{'path': path, 'content': hashlib.sha256(Path(path).read_bytes()).hexdigest()} for path in task['images']])
        fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        safe_name = __import__('re').sub(r'[^\w.-]', '_', name)
        folder = self.root / 'runtime/calls' / safe_name / fingerprint
        cancelled=read(folder/'usage.json',{}).get('status')=='cancelled'
        if cancelled and not (folder/'result.json').is_file():
            archive=self.root/'runtime/cancelled-calls'/safe_name/(fingerprint+'-'+str(time.time_ns()))
            archive.parent.mkdir(parents=True,exist_ok=True)
            if not folder.resolve().is_relative_to(self.root/'runtime') or not archive.resolve().is_relative_to(self.root/'runtime'):
                raise ValueError('取消记录需要保留在当前项目中')
            folder.rename(archive)
        folder.mkdir(parents=True, exist_ok=True)
        from .progress import tick
        if (folder / 'result.json').is_file():
            tick(self.root,name,'reused')
            return read(folder / 'result.json')
        record = read(folder / 'usage.json', {})
        if record.get('status') in {'started', 'uncertain'} and not (folder / 'response.json').is_file():
            receipt=read(folder/'receipt.json',{})
            if receipt.get('failure_kind')=='output_limit':
                raise AgentCallFailure('output_limit','已有任务超过模型输出上限，需要拆小后继续：'+name)
            raise AgentCallFailure(record.get('failure_kind') or 'uncertain','已有请求尚未确认结果，按原请求记录核对后再恢复：' + name)
        adapter = ADAPTERS[self.provider]()
        if task['images'] and not adapter.capabilities.get('images'):
            raise ValueError('当前后端未声明支持图片，任务保留完整材料等待切换')
        save(folder / 'schema.json', schema)
        (folder / 'prompt.txt').write_text(task['prompt'], encoding='utf-8')
        started = time.monotonic()
        with SLOTS:
            tick(self.root,name,'running')
            save(folder / 'usage.json', {'task': name, 'model': self.model, 'reasoning_effort': self.effort, 'role': self.role, 'status': 'started', 'round': state.get('round', 0)})
            try:
                if (folder / 'response.json').is_file():
                    value, receipt = read(folder / 'response.json'), read(folder / 'receipt.json', {})
                else:
                    value, receipt = adapter.execute(task, folder)
                formatted, changes = author_format(value)
                changes += remove_empty_extras(formatted, schema)
                for key in ('$schema', '$id'):
                    if key not in schema.get('properties', {}):
                        formatted.pop(key, None)
                jsonschema.Draft202012Validator(schema).validate(formatted)
                save(folder / 'result.json', formatted)
                save(folder / 'format-conversions.json', changes)
                save(folder / 'usage.json', dict(receipt, task=name, model=self.model, reasoning_effort=self.effort,
                     role=self.role, status='completed', round=state.get('round', 0), elapsed_seconds=round(time.monotonic()-started, 3)))
                tick(self.root,name,'completed')
                return formatted
            except Exception as error:
                tick(self.root,name,'failed')
                receipt=read(folder/'receipt.json',{})
                save(folder / 'usage.json', dict(read(folder / 'usage.json', {}),receipt=receipt,status='uncertain' if not (folder / 'response.json').is_file() else 'invalid',
                     failure_kind=getattr(error,'kind',None),usage=receipt.get('usage',[]),usage_measurement=receipt.get('usage_measurement','unavailable'),
                     error_type=type(error).__name__, elapsed_seconds=round(time.monotonic()-started, 3)))
                raise
