"""把真实脚本和数据补入材料，再修订旧限制、补写职责并等待独立审查"""
from __future__ import annotations

import importlib.util
from pathlib import Path


def _module(name):
    spec = importlib.util.spec_from_file_location('readable_' + name, Path(__file__).with_name(name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


_sources = _module('book_sources')
_amendments = _module('book_inventory_amendments')


def refresh_section(runtime, root, context):
    """先保存新增原句和未完成来源，重启时仍能找到需要补写的职责"""
    work = runtime.work_root(root) / 'sections' / context['section_id']
    raw = runtime.read(work / 'raw-sources.json')
    pack = runtime.read(work / 'source-pack.json')
    inventory = runtime.read(work / 'coverage-inventory.json')
    revised_raw, revised_pack, added = _sources.refresh_readable_resource_sources(root, raw, pack, work)
    state_path = work / 'readable-resources-refresh.json'
    state = runtime.read(state_path) if state_path.is_file() else {}
    pending = sorted(set(state.get('pending_source_ids', [])) | set(added))
    if added:
        archive = work / 'readable-resources-before'
        if not (archive / 'source-pack.json').is_file():
            for name, value in [('raw-sources', raw), ('source-pack', pack), ('coverage-inventory', inventory)]:
                runtime.save(archive / (name + '.json'), value)
        state['status'] = 'needs_real_points'
    state.setdefault('status', 'needs_real_points' if pending else 'unchanged')
    state['pending_source_ids'] = pending
    # 先保存待办再保存正文，避免进程在两次写入之间退出后丢失新增职责
    runtime.save(state_path, state)
    runtime.save(work / 'raw-sources.json', revised_raw)
    runtime.save(work / 'source-pack.json', revised_pack)
    return work, state


def complete_section(runtime, root, context):
    """逐节保留旧事实，只为真实新增内容补点和改写对应问题"""
    work = runtime.work_root(root) / 'sections' / context['section_id']
    state_path = work / 'readable-resources-refresh.json'
    state = runtime.read(state_path)
    expanded = state.get('status') == 'inventory_expanded'
    pack = runtime.read(work / 'source-pack.json')
    inventory = runtime.read(work / 'coverage-inventory.json')
    revised, amended_qids, _ = _amendments.amend_inventory(runtime, root, context, work, pack, inventory)
    # 完成状态里的历史 question_ids 用于回看，只有未完成状态才继续排队
    qids = set(state.get('question_ids', [])) if state.get('status') in ['inventory_expanded', 'needs_rewrite'] else set()
    qids.update(amended_qids)
    if revised != inventory:
        state.update(status='inventory_expanded' if expanded else 'needs_rewrite', question_ids=sorted(qids))
        runtime.save(state_path, state)
        runtime.save(work / 'coverage-inventory.json', revised)
        inventory = revised
    pending = state.get('pending_source_ids', [])
    feedback = {
        'new_text_source_ids': pending,
        'actual_problem': '完整脚本、配置和数据已经加入材料，需要据此讲清实际内容',
        'required_action': '阅读新增真实原文，解释启动模式、参数、条件、数据列及实际规则，保留全部旧点和冻结问题，新增职责另加信息点，材料整理字段留在 Debug'}
    if pending and state.get('status') != 'inventory_expanded':
        pack, inventory, added_qids = runtime._expand_section_inventory(
            root, context, work, pack, inventory, feedback, 'readable-resource')
        qids.update(added_qids)
        state.update(status='inventory_expanded', question_ids=sorted(qids))
        runtime.save(state_path, state)
    if not qids:
        return {'section_id': context['section_id'], 'changed': False}
    units = runtime.read(work / 'units.json')
    runtime._repair_section_units(root, context, work, pack, inventory, units, qids, feedback, 'readable-resource')
    candidate = work / 'candidate.json'
    if candidate.is_file():
        archive = work / 'readable-resources-candidates'
        number = len(list(archive.glob('candidate-*.json'))) + 1
        runtime.save(archive / f'candidate-{number:04d}.json', runtime.read(candidate))
        candidate.unlink()
    state.update(status='rewritten_for_independent_review', pending_source_ids=[], question_ids=sorted(qids))
    runtime.save(state_path, state)
    runtime.log(root, context['section_id'] + ' 已补写真实材料职责，等待独立审查')
    return {'section_id': context['section_id'], 'changed': True, 'question_ids': sorted(qids)}


def ensure_readable_materials(runtime, root, context_list, workers=3):
    """所有材料先保存真实正文，再并行补写，最终覆盖仍由后续独立审查确认"""
    root = Path(root).resolve()
    for context in context_list:
        refresh_section(runtime, root, context)
    return runtime.parallel_sections(root, context_list,
        lambda context: complete_section(runtime, root, context), workers)
