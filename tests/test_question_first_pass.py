"""验证第 0 章、按需补齐和来源继承，全程不调用真实模型"""
import copy
import json
from pathlib import Path
import pytest

from lessonweave import pipeline, planning
from lessonweave.storage import read, save
from build_questions import publish_questions, mapping_report, check_questions
from build_chapters import publish_chapters, check_chapters, generation_tree, chapter_document
from source_disposition import apply_patch
import book_sources


def q(qid, sources, children=None):
    return {'id': qid, 'premise': '读者需要理解材料时，', 'question': '怎样说明' + qid + '负责的内容？',
            'intent': '解释本题对应的真实材料', 'source_nodes': sources, 'depends_on': [], 'children': children or []}


def fixture(root, metadata=True):
    pipeline.scaffold(root)
    nodes = [{'id': 'n3', 'type': 'paragraph', 'text': '系统按 16 MB 配置容量', 'children': []},
             {'id': 'n4', 'type': 'paragraph', 'text': '系统按最终配置量计算占用', 'children': []}]
    children = [{'id': 'n2', 'type': 'section', 'text': '容量配置', 'children': nodes}]
    if metadata:
        children.insert(0, {'id': 'n1', 'type': 'paragraph', 'text': '作者与日期', 'children': []})
    material = {'run': 'run1', 'tree': {'id': 'n0', 'type': 'document', 'text': '', 'children': children}, 'validation': {'passed': True, 'errors': []}}
    save(root / '01_tree/tree.json', material)
    save(root / '01_tree/history/run1/tree.json', material)
    body = q('q.1', ['n2'], [q('q.1.1', ['n2'])])
    groups = [q('q.0', ['n1'], [q('q.0.1', ['n1'])])] if metadata else []
    groups.append(body)
    doc = {'title': '怎样配置容量', 'goal': '理解容量与占用', 'starting_point': '能阅读简单数据',
           'range_description': '材料中的容量配置', 'tree': q('q.root', ['n0'], groups),
           'learning_order': (['q.0.1'] if metadata else []) + ['q.1.1']}
    response = {'questions': doc, 'metadata': {'present': metadata, 'source_nodes': ['n1'] if metadata else [], 'reason': '原件提供作者与日期' if metadata else '原件只有正文'},
                'dispositions': [{'source_nodes': ['n2'], 'extent': 'node', 'role': 'structure', 'question_ids': [], 'destination': '章节结构', 'reason': '标题定位下方正文'}]}
    save(root / '00_source/input.json', {'kind': 'file', 'material': 'sample.txt', 'mode': 'full_material', 'system_prompt': ''})
    return material, response


class Replay:
    provider = 'codex'

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def call(self, name, prompt, schema, **kwargs):
        self.calls.append((name, prompt, kwargs))
        return copy.deepcopy(self.responses.pop(0))


def test_first_complete_pass_skips_fill_and_does_not_start_chapters(tmp_path):
    # 首轮已分配完整时只请求一次，重复进入复用结果，也不偷偷进入章节和写作
    _, response = fixture(tmp_path)
    backend = Replay([response])
    result = planning.run_questions(tmp_path, backend)
    assert result['validation']['passed']
    assert result['coverage']['percentage'] == result['coverage']['teaching_percentage'] == 100
    assert len(backend.calls) == 1 and backend.calls[0][2]['read_only_tools']
    assert '完整材料树位于' in backend.calls[0][1]
    assert '系统按 16 MB' not in backend.calls[0][1]
    assert not (tmp_path / '03_chapters/chapters.json').exists()
    assert not (tmp_path / '05_writing/book.json').exists()
    assert planning.run_questions(tmp_path, backend) == result
    assert len(backend.calls) == 1


def test_missing_preface_and_body_are_filled_without_rewriting_existing_question(tmp_path):
    # 首轮缺少作者问题和一段正文时，只补第 0 章和真实缺项，原问题编号与内容保持原样
    _, complete = fixture(tmp_path)
    initial = copy.deepcopy(complete)
    initial['questions']['tree']['children'].pop(0)
    initial['questions']['learning_order'] = ['q.1.1']
    old = initial['questions']['tree']['children'][0]['children'][0]
    old['source_nodes'] = ['n3']
    patch = {'new_questions': [{'parent_question_id': 'q.root', 'after_question_id': '', 'question': complete['questions']['tree']['children'][0]}],
             'question_updates': [], 'source_additions': [{'question_id': 'q.1.1', 'source_nodes': ['n4'], 'use': 'teach', 'reason': '本题需要同时解释占用量'}],
             'dispositions': [], 'learning_order': []}
    backend = Replay([initial, patch])
    result = planning.run_questions(tmp_path, backend)
    assert len(backend.calls) == 2 and '-fill-' in backend.calls[1][0]
    assert result['validation']['passed'] and result['learning_order'] == ['q.0.1', 'q.1.1']
    body = result['tree']['children'][1]['children'][0]
    assert body['question'] == old['question'] and body['source_nodes'] == ['n3', 'n4']
    assert len(read(tmp_path / 'runtime/question-planning.json')['rounds']) == 2


def test_material_without_metadata_has_no_artificial_chapter_zero(tmp_path):
    # 原件只有正文时不制造第 0 章，也不为不存在的元数据触发补齐请求
    _, response = fixture(tmp_path, metadata=False)
    backend = Replay([response])
    result = planning.run_questions(tmp_path, backend)
    assert result['validation']['passed'] and result['coverage']['preface_questions'] == 0
    assert len(backend.calls) == 1


def test_old_disposition_cannot_hide_actual_preface_source(tmp_path):
    # 后加第 0 章时，旧查阅用途继续保留原问题，但不能遮住新问题的真实引用
    material, response = fixture(tmp_path)
    response['dispositions'].append({'source_nodes': ['n1'], 'extent': 'node', 'role': 'reference',
                                     'question_ids': ['q.1.1'], 'destination': '旧查阅位置', 'reason': '保留旧引用'})
    result = publish_questions(tmp_path, planning.question_document(material, response))
    report = mapping_report(result, tmp_path)
    row = next(r for r in report['nodes'] if r['material_node'] == 'n1')
    assert row['question_ids'] == ['q.0.1', 'q.1.1']
    owners = book_sources.planned_question_owners(result, material, [result['tree']['children'][0]['children'][0]])
    assert owners['n1'] == ['q.0.1']


def test_branch_assignment_reaches_later_material_selection(tmp_path):
    # 问题选中完整章节分支后，后续取材同样取得两个正文节点，标题只保留结构用途
    material, response = fixture(tmp_path)
    document = planning.question_document(material, response)
    owners = book_sources.planned_question_owners(document, material, [document['tree']['children'][1]['children'][0]])
    assert owners['n3'] == owners['n4'] == ['q.1.1'] and not owners['n2']


def test_link_without_a_real_destination_stays_missing(tmp_path):
    # 重复入口指向不存在的目标时继续列为缺项，不能仅凭 duplicate 标签获得覆盖
    material, response = fixture(tmp_path)
    material['tree']['children'].append({'id': 'n5', 'type': 'symlink', 'text': '入口', 'children': []})
    material['representation_links'] = {'n5': {'targets': ['absent'], 'method': 'resolved_symlink', 'reason': '原目标缺失'}}
    save(tmp_path / '01_tree/history/run1/tree.json', material)
    document = planning.question_document(material, response)
    assert mapping_report(document, tmp_path)['summary']['unmapped'] == ['n5']


def chapter_candidate(question):
    def title(tid, kind, premise, text, ids, children=None):
        return {'id': tid, 'kind': kind, 'premise': premise, 'question': text, 'title': premise + text,
                'focus': '组织对应问题的理解顺序', 'question_ids': ids, 'source_nodes': [], 'requires': [], 'children': children or []}
    root = title('book', 'book', '读者要理解整份材料时，', '怎样组织阅读？', ['q.root'], [
        title('c0', 'chapter', '开始阅读之前，', '怎样确认材料身份？', ['q.0'], [title('s0', 'section', '原件提供署名时，', '怎样辨认作者与日期？', ['q.0.1'])]),
        title('c1', 'chapter', '系统按步长配置容量时，', '怎样确定占用？', ['q.1'], [title('s1', 'section', '目标容量确定后，', '怎样选择配置量？', ['q.1.1'])])])
    return {'profile': 'chapter-outline-v1', 'question_tree': f"02_questions/history/{question['question_run']}/questions.json", 'question_run': question['question_run'],
            'material_tree': question['material_tree'], 'material_run': question['material_run'], 'tree': root, 'learning_order': [], 'validation': {'passed': False, 'errors': []}}


def test_chapters_preserve_zero_and_exactly_one_owner_per_question(tmp_path):
    # 第 0 章保持 0.，正文从 1. 开始，全部五个问题各归属一次并保留原材料引用
    material, response = fixture(tmp_path)
    question = publish_questions(tmp_path, planning.question_document(material, response))
    result = publish_chapters(tmp_path, chapter_candidate(question))
    assert result['validation']['passed'] and result['coverage']['percentage'] == 100
    assert result['coverage']['assignments'] == result['coverage']['question_nodes'] == 5
    assert result['tree']['children'][0]['title'].startswith('0. ')
    assert result['tree']['children'][0]['children'][0]['title'].startswith('0.1. ')
    assert result['tree']['children'][1]['title'].startswith('1. ')
    assert result['tree']['children'][1]['children'][0]['source_nodes'] == ['n2']
    duplicate = copy.deepcopy(result)
    duplicate['tree']['question_ids'].append('q.1.1')
    duplicate.pop('coverage')
    assert any('重复分配' in e for e in check_chapters(duplicate, tmp_path))
    missing = copy.deepcopy(result)
    missing['tree']['children'][1]['children'][0]['question_ids'] = []
    missing.pop('coverage')
    assert any('q.1.1' in e for e in check_chapters(missing, tmp_path))


def test_root_reference_and_body_exclusion_cannot_manufacture_coverage(tmp_path):
    # 具体问题不能引用整棵材料根节点，也不能把直接讲解的正文同时标为排除
    material, response = fixture(tmp_path)
    document = planning.question_document(material, response)
    document['tree']['children'][1]['children'][0]['source_nodes'] = ['n0', 'n3']
    document['dispositions'].append({'source_nodes': ['n3'], 'extent': 'node', 'role': 'excluded',
                                     'question_ids': [], 'destination': '排除', 'reason': '错误示例'})
    errors = check_questions(document, tmp_path)
    assert any('整棵材料根节点' in e for e in errors)
    assert any('同时被排除' in e for e in errors)


def test_common_planning_entry_skips_fact_inventory_and_calls_two_stages(tmp_path, monkeypatch):
    # 完整规划入口只调用问题和章节两个任务，逐事实清点和承接正文均不提前生成
    _, response = fixture(tmp_path)
    import information_points
    monkeypatch.setattr(information_points, 'build', lambda *args: (_ for _ in ()).throw(AssertionError('旧全局清点被调用')))
    calls = []

    class Backend:
        provider = 'codex'

        def call(self, name, prompt, schema, **kwargs):
            calls.append(name)
            if name.startswith('02_questions'):
                return copy.deepcopy(response)
            assert name == '03_chapters'
            return chapter_candidate(read(tmp_path / '02_questions/questions.json'))

    result = planning.run_planning(tmp_path, Backend())
    assert result['validation']['passed']
    assert len(calls) == 2 and calls[0].startswith('02_questions-initial') and calls[1] == '03_chapters'
    assert not (tmp_path / '01_tree/points.json').exists()
    assert not (tmp_path / '05_writing/book.json').exists()


def test_question_working_copy_upgrades_scripts_and_preserves_previous_outputs(tmp_path):
    # 续跑更新旧工作副本时只替换实现，先归档旧脚本，正文与用户笔记原字节保留
    stage = tmp_path / '02_questions'
    stage.mkdir()
    (stage / 'generation.md').write_text('旧提示词', encoding='utf-8')
    (stage / 'material_context.py').write_text('old input adapter', encoding='utf-8')
    save(tmp_path / '05_writing/book.json', {'text': '既有正文'})
    save(tmp_path / 'notes.json', {'text': '用户笔记'})
    before = {path: path.read_bytes() for path in [tmp_path / '05_writing/book.json', tmp_path / 'notes.json']}
    planning.sync_stages(tmp_path, ('02_questions',))
    assert (tmp_path / 'runtime/framework-history/questions-v2/02_questions/generation.md').read_text(encoding='utf-8') == '旧提示词'
    assert not (stage / 'material_context.py').exists()
    assert all(path.read_bytes() == content for path, content in before.items())


def test_chapter_missing_assignment_uses_one_focused_patch(tmp_path):
    # 章节候选只漏一问时，补齐只改归属，原问题树不变，输入不重复携带原件或逐节点用途
    material, response = fixture(tmp_path)
    question = publish_questions(tmp_path, planning.question_document(material, response))
    before = (tmp_path / '02_questions/questions.json').read_bytes()
    candidate = chapter_candidate(question)
    candidate['tree']['children'][1]['children'][0]['question_ids'] = []
    patch = {'new_titles': [], 'title_updates': [], 'question_assignments': [{'question_id': 'q.1.1', 'title_id': 's1'}], 'child_orders': []}
    backend = Replay([candidate, patch])
    result = planning.run_chapters(tmp_path, backend)
    assert result['validation']['passed'] and result['coverage']['percentage'] == 100
    assert len(backend.calls) == 2 and backend.calls[1][0].startswith('03_chapters-fill-')
    assert '系统按 16 MB' not in backend.calls[0][1]
    assert 'representation_links' not in backend.calls[0][1]
    assert (tmp_path / '02_questions/questions.json').read_bytes() == before


def test_chapter_model_returns_only_directory_and_script_inherits_existing_relations(tmp_path):
    # 模型只安排目录，脚本记录目录顺序并继承已有来源和依赖，不让模型重复填写派生字段
    from jsonschema import Draft202012Validator
    material, response = fixture(tmp_path)
    response['questions']['tree']['children'][1]['children'][0]['depends_on'] = ['q.0.1']
    question = publish_questions(tmp_path, planning.question_document(material, response))
    minimal = {'tree': generation_tree(chapter_candidate(question)['tree'])}
    captured = []

    class Backend:
        def call(self, name, prompt, schema, **kwargs):
            Draft202012Validator(schema).validate(minimal)
            captured.append(schema)
            assert set(schema['properties']) == {'tree'}
            assert set(schema['$defs']['title']['properties']) == {
                'id', 'kind', 'premise', 'question', 'focus', 'question_ids', 'children'}
            return copy.deepcopy(minimal)

    result = planning.run_chapters(tmp_path, Backend())
    assert len(captured) == 1 and result['validation']['passed']
    assert result['learning_order'] == ['q.0.1', 'q.1.1']
    section = result['tree']['children'][1]['children'][0]
    assert section['source_nodes'] == ['n2'] and section['requires'] == ['s0']
    assert section['title'] == '1.1. ' + section['premise'] + section['question']
    Draft202012Validator(read(tmp_path / '03_chapters/chapters.schema.json')).validate(result)
    assert not (tmp_path / '05_writing/book.json').exists()


def test_chapter_generation_schema_rejects_script_placeholders(tmp_path):
    # 生成格式不接受空的顺序占位，保存格式仍然要求实际的非空顺序，避免两份要求相互矛盾
    from jsonschema import Draft202012Validator
    material, response = fixture(tmp_path)
    question = publish_questions(tmp_path, planning.question_document(material, response))
    minimal = {'tree': generation_tree(chapter_candidate(question)['tree'])}
    schema = read(tmp_path / '03_chapters/generation.schema.json')
    validator = Draft202012Validator(schema)
    validator.validate(minimal)
    invalid = dict(minimal, learning_order=[])
    assert list(validator.iter_errors(invalid))
    invalid = copy.deepcopy(minimal)
    invalid['tree']['source_nodes'] = []
    assert list(validator.iter_errors(invalid))
    candidate = chapter_document(question, minimal)
    assert candidate['question_run'] == question['question_run']
    assert 'learning_order' not in candidate


def test_minimal_new_section_patch_receives_script_fields_when_saved(tmp_path):
    # 补齐模型新增小节时同样只填写目录字段，新增小节的来源和完整标题由脚本补齐
    from jsonschema import Draft202012Validator
    material, response = fixture(tmp_path)
    question = publish_questions(tmp_path, planning.question_document(material, response))
    minimal = {'tree': generation_tree(chapter_candidate(question)['tree'])}
    section = minimal['tree']['children'][1]['children'].pop()
    patch = {'new_titles': [{'parent_title_id': 'c1', 'after_title_id': '', 'title': section}],
             'title_updates': [], 'question_assignments': [], 'child_orders': []}
    Draft202012Validator(read(tmp_path / '03_chapters/patch.schema.json')).validate(patch)
    backend = Replay([minimal, patch])
    result = planning.run_chapters(tmp_path, backend)
    assert len(backend.calls) == 2 and result['validation']['passed']
    saved = result['tree']['children'][1]['children'][0]
    assert saved['source_nodes'] == ['n2'] and saved['title'].startswith('1.1. ')


def test_old_coverage_summary_is_recomputed_without_a_model_call(tmp_path):
    # 实现升级只改变派生统计时由脚本重算，不把已完成的问题重新发给模型
    material, response = fixture(tmp_path)
    document = publish_questions(tmp_path, planning.question_document(material, response))
    document['coverage']['links'] += 1
    save(tmp_path / '02_questions/questions.json', document)
    backend = Replay([])
    result = planning.run_questions(tmp_path, backend)
    assert result['validation']['passed'] and not backend.calls


@pytest.mark.parametrize('tools', [False, True])
def test_codex_preserves_login_configuration_and_only_enables_requested_read_tools(tmp_path, monkeypatch, tools):
    # 本机 CLI 沿用用户登录配置，只有读取材料的任务打开 shell，测试使用本地进程替身
    from lessonweave import agents
    captured = []

    class Process:
        pid = 1234
        returncode = 0

        def __init__(self, args, **kwargs):
            captured.extend(args)
            self.output = kwargs['stdout']
            self.response = Path(args[args.index('-o') + 1])

        def communicate(self, prompt, timeout=None):
            self.response.write_text('{"ok":true}', encoding='utf-8')
            self.output.write(json.dumps({'type': 'turn.completed', 'usage': {'input_tokens': 1, 'output_tokens': 1}}) + '\n')
            self.output.flush()

    monkeypatch.setattr(agents, 'codex_executable', lambda: 'local-test-cli')
    monkeypatch.setattr(agents.subprocess, 'Popen', Process)
    value, _ = agents.CodexAdapter().execute({'schema': {}, 'model': 'fixture', 'effort': 'high', 'images': [],
                                            'prompt': '测试', 'read_only_tools': tools}, tmp_path)
    assert value == {'ok': True}
    assert '--ignore-user-config' not in captured
    assert captured[captured.index('-s') + 1] == 'read-only'
    assert 'features.shell_tool=' + str(tools).lower() in captured


def test_pdf_position_links_preserve_different_text_without_case_specific_paths():
    # 文本相同且位置对应时关联同内容，文字不同则保留差异，不依赖某份论文的固定目录
    from source_disposition import representation_links
    native = {'id': 'a', 'type': 'text', 'text': '容量 16 MB', 'children': [],
              'source': {'provenance': [{'page_no': 1, 'bbox': {'l': 0, 't': 0, 'r': 100, 'b': 20, 'coord_origin': 'TOPLEFT'}}]}}
    exact = {'id': 'b', 'type': 'source_text', 'text': '容量16 MB', 'source': {'page': 1, 'bbox': [0, 0, 100, 20]}, 'children': []}
    variant = {'id': 'c', 'type': 'source_text', 'text': '另一种识别结果', 'source': {'page': 1, 'bbox': [0, 0, 100, 20]}, 'children': []}
    material = {'tree': {'id': 'root', 'type': 'document', 'children': [native, exact, variant]}}
    links = representation_links(material)
    assert links['b']['targets'] == ['a'] and links['b']['method'] == 'exact_text_and_position'
    assert links['c']['targets'] == ['a'] and links['c']['method'] == 'position_variant_preserved'
    assert variant['text'] == '另一种识别结果'
