"""复用正式 harness 完成一次生成、首次独立审查和一次内容批量返修"""
import copy
import concurrent.futures as futures
import shutil
import time
from pathlib import Path
import jsonschema
from . import pipeline as pipe
from .agents import Backend
from .storage import read, save, Store
from .findings import record


def run_three_phases(root):
    root = Path(root).resolve()
    flow, authoring = pipe.flow, pipe.authoring
    prior = read(root / 'experiment.json', {})
    if prior.get('policy', {}).get('on_error') == 'stop_and_preserve':
        history = root / 'history/attempt-0001'
        history.mkdir(parents=True, exist_ok=True)
        for name in ('experiment.json', 'run-result.json', 'run_three_stages.py'):
            if (root / name).is_file() and not (history / name).exists():
                shutil.copyfile(root / name, history / name)
        prior_seconds = sum(p.get('elapsed_seconds', 0) for p in prior.get('phases', []))
        state = read(root / 'runtime/state.json', {})
        state['feedback'] = {}
        save(root / 'runtime/state.json', state)
        report = {'source': read(root / '00_source/input.json')['material'],
                  'model': 'gpt-6.1-sol', 'effort': 'high', 'started_at': time.time(),
                  'prior_generation_seconds': prior_seconds, 'phases': [], 'status': 'running',
                  'policy': {'generation_passes': 1, 'independent_review_passes': 1,
                             'batch_revision_passes': 1, 'final_model_review': False,
                             'on_error': 'repair_and_continue', 'mid_run_edits': False,
                             'behaviors': ['decompose', 'generate', 'check', 'repair']}}
    else:
        report = prior or {'phases': [], 'status': 'running', 'policy': {'on_error': 'repair_and_continue'}}

    def persist():
        calls = [read(p) for kind in ('calls', 'recovery-calls') for p in (root / ('runtime/' + kind)).glob('*/*/usage.json')]
        for index, row in enumerate(report['phases']):
            selected = [c for c in calls if (index == 0 and c.get('round', 0) == 0 and c.get('role') != 'independent_review')
                        or (index == 1 and c.get('role') == 'independent_review')
                        or (index == 2 and c.get('round') == 1 and c.get('role') != 'independent_review')]
            totals = {'calls': len(selected), 'input_tokens': 0, 'output_tokens': 0,
                      'cached_input_tokens': 0, 'usage_missing_calls': 0}
            for call in selected:
                if not call.get('usage'):
                    totals['usage_missing_calls'] += 1
                for usage in call.get('usage', []):
                    for key in ('input_tokens', 'output_tokens', 'cached_input_tokens'):
                        totals[key] += usage.get(key, 0)
            row['usage'] = totals
        report['calls'] = calls
        save(root / 'experiment.json', report)

    def snapshot(name):
        target = root / 'versions' / name
        for stage in pipe.STAGES:
            shutil.copytree(root / stage, target / stage, dirs_exist_ok=True)
        Store(root / 'site-data').register(name, 'Olympus · ' + name, target, legacy=True)

    def execute_phase(name, operation):
        row = next((p for p in report['phases'] if p['name'] == name), None)
        if row and row['status'] == 'completed':
            return
        if row is None:
            row = {'name': name, 'started_at': time.time(), 'status': 'running'}
            report['phases'].append(row)
        persist()
        print(name + ' started', flush=True)
        pipe.recover(root, name, operation)
        row.update(status='completed', ended_at=time.time())
        row['active_elapsed_seconds'] = row['ended_at'] - row['started_at']
        row['elapsed_seconds'] = row['active_elapsed_seconds'] + (report.get('prior_generation_seconds', 0) if len(report['phases']) == 1 else 0)
        persist()
        print(name + ' completed', flush=True)

    def generate():
        pipe.update_state(root, round=0, maximum=1, status='running', behavior='decompose')
        pipe.scaffold(root)
        pipe.prepare(root)
        flow.tree_stages(root, Backend(root, role='planning'))
        pipe.update_state(root, behavior='generate')
        pipe.write_sections(root, Backend(root, role='writing'), reviewed=False)
        snapshot('initial')

    def review():
        pipe.update_state(root, behavior='check')
        contexts, _, chapters, questions = flow.runtime.contexts(root)
        overview = read(root / '05_writing/work/overview.json')
        def inspect(context):
            context = flow.runtime.patch_context(context, chapters, questions, overview)
            context.update(opening_title='', writing_contract_version=authoring.VERSION)
            folder = root / '05_writing/work/sections' / context['section_id']
            return pipe.review_section(root, context, folder, read(folder / 'source-pack.json'),
                                       read(folder / 'coverage-inventory.json'), read(folder / 'units.json'), read(folder / 'extras.json'))
        with futures.ThreadPoolExecutor(max_workers=3) as pool:
            documents = pipe.collect(pool, contexts, inspect, root)
        checked = []
        for doc in documents:
            folder = root / '05_writing/work/sections' / doc['section_id']
            checked.append({'section_id': doc['section_id'], 'validation': doc['validation'],
                            'review': read(folder / 'review.json'), 'coverage': read(folder / 'coverage.json')})
        save(root / 'first-review.json', {'sections': checked})
        snapshot('reviewed-initial')

    def repair():
        pipe.update_state(root, round=1, behavior='repair')
        sections, _, _ = pipe.write_sections(root, Backend(root, role='writing'), reviewed=False, frozen_materials=True)
        checks = []
        schema = read(flow.FRAME / '05_writing/demo.schema.json')
        for sid, doc in sections.items():
            issues = [e.json_path + ': ' + e.message for e in jsonschema.Draft202012Validator(schema).iter_errors(doc)]
            issues.extend(r['location'] + ': ' + r['code'] for r in authoring.surface_findings(doc) if r['severity'] == 'error')
            record(root, sid, issues)
            checks.append({'section_id': sid, 'format_passed': not issues, 'issues': issues})
        save(root / 'final-script-checks.json', {'model_review': False, 'sections': checks})
        book = read(root / '05_writing/preview-book.json')
        book.update(preview_status='批量返修稿，首次审查记录单独保留，本稿按约定不再复审')
        save(root / '05_writing/preview-book.json', book)
        snapshot('revised')

    persist()
    execute_phase('一次有效生成', generate)
    execute_phase('首次独立审查', review)
    execute_phase('一次内容批量返修', repair)
    report.update(status='completed_three_phases', final_review_status='not_re_reviewed_by_design')
    report['review_and_revision_over_generation'] = sum(p['elapsed_seconds'] for p in report['phases'][1:]) / report['phases'][0]['elapsed_seconds']
    pipe.update_state(root, status='completed', quality_status='findings_recorded', behavior='repair')
    persist()
    return report
