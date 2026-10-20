"""首次同时规划第 0 章和正文，脚本列差集后只补缺项"""
import copy
import json
from pathlib import Path
import shutil
import sys
from .storage import read, save
from .metrics import span

FRAME = Path(__file__).resolve().parents[1] / 'framework'
for stage in ['02_questions', '03_chapters']:
    path = str(FRAME / stage)
    if path not in sys.path:
        sys.path.insert(0, path)


def sync_stages(root, stages=('02_questions', '03_chapters')):
    root = Path(root).resolve()
    if '05-test' in root.parts:
        raise ValueError('05-test 保持原样')
    for stage in stages:
        target = root / stage
        target.mkdir(parents=True, exist_ok=True)
        for source in (FRAME / stage).iterdir():
            if not source.is_file() or source.suffix not in {'.py', '.md', '.json'}:
                continue
            destination = target / source.name
            if destination.resolve() == source.resolve() or destination.is_file() and destination.read_bytes() == source.read_bytes():
                continue
            if destination.is_file():
                archive = root / 'runtime/framework-history/questions-v2' / stage / source.name
                if not archive.exists():
                    archive.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(destination, archive)
            shutil.copy2(source, destination)
        # 旧输入压缩器已经不参与文件读取式规划
        old = target / 'material_context.py'
        if old.is_file() and root != FRAME:
            archive = root / 'runtime/framework-history/questions-v2' / stage / old.name
            archive.parent.mkdir(parents=True, exist_ok=True)
            if not archive.exists():
                shutil.copy2(old, archive)
            old.unlink()


def fixed_fields(material):
    return {'profile': 'learning-questions-v1', 'scope': 'full_material', 'planning_version': 2,
            'material_tree': f"01_tree/history/{material['run']}/tree.json", 'material_run': material['run'],
            'source_roots': [material['tree']['id']], 'context_nodes': [], 'validation': {'passed': False, 'errors': []}}


def question_document(material, response, root=None):
    from source_disposition import representation_links
    return {**copy.deepcopy(response['questions']), **fixed_fields(material),
            'metadata': copy.deepcopy(response['metadata']), 'dispositions': copy.deepcopy(response['dispositions']),
            'representation_links': representation_links(material, root)}


def question_prompt(root, material, initial=True, tools=True):
    root = Path(root)
    stage = root / '02_questions'
    prompt = (stage / 'generation.md').read_text(encoding='utf-8')
    objective = read(root / '00_source/input.json', {})
    prompt += '\n用户目标\n' + json.dumps(objective, ensure_ascii=False)
    material_path = root / fixed_fields(material)['material_tree']
    if tools:
        prompt += f'\n完整材料树位于 {material_path}，只读工具：{sys.executable} {stage / "read_material.py"} {material_path} list [ID]、get ID、subtree ID、find 正则、file 相对路径；也可以直接用只读 Python 读取当前材料与原件，没有节点、文件或字符截断上限\n'
    elif initial:
        prompt += '\n完整材料\n' + json.dumps(material, ensure_ascii=False, separators=(',', ':'))
    if initial:
        assets = planning_images(root, material)
        if assets:
            prompt += '\n随请求附上全部公式与插图，图片顺序对应以下路径，可以按材料节点中的 asset 核对来源\n' + json.dumps(assets, ensure_ascii=False)
        prompt += '\n首次同时规划 q.0 和正文问题，返回完整 questions、metadata、dispositions，第 0 章只生成问题，不生成任何答案或讲解\n'
    else:
        prompt += f'\n只补当前差集：读取 {stage / "missing-index.json"}、{stage / "questions.json"} 中的相关职责及必要原件，只返回 patch.schema.json 指定的修改块\n'
        if not tools:
            current = read(stage / 'questions.json')
            pending = read(stage / 'missing-index.json')
            prompt += json.dumps({'missing': pending, 'questions': current['tree'], 'metadata': current['metadata']}, ensure_ascii=False)
    return prompt


def planning_images(root, material):
    from source_disposition import walk
    images = []
    for node in walk(material['tree']):
        asset = node.get('asset') or node.get('content', {}).get('asset')
        if not asset:
            continue
        path = Path(asset)
        if not path.is_absolute():
            path = Path(material.get('asset_base') or root) / asset.lstrip('/')
        if path.is_file() and path.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp'}:
            images.append(str(path))
    return list(dict.fromkeys(images))


def run_questions(root, backend=None):
    from .agents import Backend
    from build_questions import publish_questions, check_questions
    from source_disposition import apply_patch
    root = Path(root).resolve()
    sync_stages(root, ('02_questions',))
    material = read(root / '01_tree/tree.json')
    # 材料树的完整快照沿用已有运行编号，不改节点和原件
    material_path = root / fixed_fields(material)['material_tree']
    if not material_path.is_file():
        save(material_path, material)
    document = read(root / '02_questions/questions.json')
    if document and document.get('material_run') == material['run']:
        content = copy.deepcopy(document)
        content.pop('coverage', None)
        if not check_questions(content, root):
            # 统计规则升级只重算派生报告，不为旧统计再次请求模型
            if check_questions(document, root):
                return publish_questions(root, content)
            with span(root, 'questions', 'reuse'):
                return document
    backend = backend or Backend(root, role='question_planning')
    tools = getattr(backend, 'provider', 'codex') == 'codex'
    initial = not document or document.get('planning_version') != 2 or document.get('material_run') != material['run']
    state_path = root / 'runtime/question-planning.json'
    rounds = read(state_path, {}).get('rounds', [])
    with span(root, 'questions', 'phase'):
        while True:
            number = len(rounds)
            mode = 'initial' if initial else 'fill'
            schema = read(root / '02_questions' / ('initial.schema.json' if initial else 'patch.schema.json'))
            name = '02_questions-' + mode + '-' + str(number).zfill(4)
            prompt = question_prompt(root, material, initial, tools)
            with span(root, 'questions', 'generation' if initial else 'repair', task=name):
                response = backend.call(name, prompt, schema, images=planning_images(root, material) if initial else [], read_only_tools=tools)
            document = question_document(material, response, root) if initial else apply_patch(document, response)
            with span(root, 'questions', 'check'):
                document = publish_questions(root, document)
            c = document['coverage']
            rounds.append({'task': name, 'mode': mode, 'question_run': document['question_run'],
                           'unmapped': len(c['unmapped']), 'preface_missing': c['preface_missing'],
                           'disposition_percentage': c['disposition_percentage'], 'teaching_percentage': c['teaching_percentage'],
                           'format_errors': document['validation']['errors']})
            save(state_path, {'workflow': 'questions-first-pass-v2', 'status': 'completed' if document['validation']['passed'] else 'filling', 'rounds': rounds})
            if document['validation']['passed']:
                return document
            initial = False


def run_chapters(root, backend=None):
    from .agents import Backend
    from build_chapters import publish_chapters, check_chapters, chapter_document, generation_tree
    root = Path(root).resolve()
    sync_stages(root, ('03_chapters',))
    qdoc = read(root / '02_questions/questions.json')
    existing = read(root / '03_chapters/chapters.json')
    if existing and existing.get('question_run') == qdoc['question_run'] and not check_chapters(existing, root):
        return existing
    backend = backend or Backend(root, role='chapter_planning')
    schema = read(root / '03_chapters/generation.schema.json')
    prompt = (root / '03_chapters/generation.md').read_text(encoding='utf-8')
    # 目录只读取问题职责和依赖，逐节点用途与重复表示也无需再发一遍
    view = {key: qdoc[key] for key in ['title', 'goal', 'starting_point', 'range_description', 'tree', 'learning_order']}
    prompt += '\n' + json.dumps({'questions': view}, ensure_ascii=False, separators=(',', ':'))
    with span(root, 'chapters', 'phase'):
        candidate = backend.call('03_chapters', prompt, schema)
        candidate = chapter_document(qdoc, candidate)
        result = publish_chapters(root, candidate)
        number = 0
        while not result['validation']['passed']:
            from build_chapters import apply_chapter_patch, derive_plan, walk
            pending = set(result['coverage']['unassigned_questions'] + result['coverage']['duplicated_questions'])
            for edge in derive_plan(result, qdoc)['conflicts']:
                pending.update([edge['before_question'], edge['after_question']])
            selected = [q for q in walk(qdoc['tree']) if q['id'] in pending]
            repair = '只修改脚本列出的归属、层级、顺序或标题格式，不改问题和来源，不生成讲解；question_assignments 为指定问题设置唯一归属，child_orders 只调整同一父标题的子标题顺序，title_updates 保留原有子树\n'
            repair += json.dumps({'errors': result['validation']['errors'], 'coverage': result['coverage'],
                                  'current_tree': generation_tree(result['tree']), 'related_questions': selected}, ensure_ascii=False, separators=(',', ':'))
            patch = backend.call('03_chapters-fill-' + str(number).zfill(4), repair, read(root / '03_chapters/patch.schema.json'))
            candidate = apply_chapter_patch(result, patch)
            result = publish_chapters(root, candidate)
            number += 1
    return result


def run_planning(root, backend=None):
    run_questions(root, backend)
    chapters = run_chapters(root, backend)
    # 这里只保存阅读器所需关系，承接正文仍在实际写作后生成
    from build_transitions import context_plan
    context_plan(Path(root), chapters)
    return chapters
