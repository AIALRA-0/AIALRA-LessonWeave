"""术语大小写位、统一整理与旧读本兼容"""
import copy
import json
import pytest
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'framework' / '05_writing'))

import lean_contract as contract
from book_terminology import format_term_metadata, normalize_term_names, term_name_findings
import independent_checks as writing_checks
import repair_batches
import migrate_term_names


def test_default_case_rules_sync_names_components_display_and_aliases():
    term = {
        'id': 'cpu', 'kind': 'initialism', 'abbreviation': 'cpu', 'chinese': '中央处理器',
        'english': 'central processing unit', 'display': 'cpu 中央处理器（central processing unit）',
        'aliases': ['cpu', 'central processing unit', 'processor'],
        'components': [
            {'symbol': 'c', 'word': 'central'},
            {'symbol': 'p', 'word': 'processing'},
            {'symbol': 'u', 'word': 'unit'},
        ],
        'definition': '定义保留', 'explanation': ['解释保留'],
    }

    normalized, changes = format_term_metadata([term])
    result = normalized[0]

    assert result['abbreviation'] == 'CPU'
    assert result['english'] == 'Central Processing Unit'
    assert result['components'] == [
        {'symbol': 'C', 'word': 'Central'},
        {'symbol': 'P', 'word': 'Processing'},
        {'symbol': 'U', 'word': 'Unit'},
    ]
    assert result['display'] == 'CPU 中央处理器（Central Processing Unit）'
    assert result['aliases'] == ['CPU', 'Central Processing Unit', 'processor']
    assert result['definition'] == term['definition']
    assert result['explanation'] == term['explanation']
    assert 'abbreviation_case_exception' not in result
    assert 'english_case_exception' not in result
    assert changes
    assert not term_name_findings(result)


def test_case_exception_one_keeps_authored_mixed_case():
    term = {
        'id': 'ph', 'kind': 'initialism', 'abbreviation': 'pH', 'chinese': '酸碱度',
        'english': 'potential of Hydrogen', 'abbreviation_case_exception': 1,
        'english_case_exception': 1, 'display': 'pH 酸碱度（potential of Hydrogen）',
        'aliases': ['pH', 'potential of Hydrogen'],
        'components': [
            {'symbol': 'p', 'word': 'potential'},
            {'symbol': 'H', 'word': 'Hydrogen'},
        ],
        'definition': '定义保持原样',
    }

    normalized = normalize_term_names(term)

    assert normalized == term
    assert not term_name_findings(normalized)


def test_case_exception_one_keeps_same_english_display_once():
    term = {
        'id': 'spring', 'kind': 'concept', 'abbreviation': None,
        'chinese': 'JST SPRING', 'english': 'JST SPRING',
        'abbreviation_case_exception': 1, 'english_case_exception': 1,
        'display': 'JST SPRING（JST SPRING）', 'aliases': ['JST SPRING', 'jst spring'],
        'components': [],
    }

    normalized = normalize_term_names(term)

    assert normalized['english'] == 'JST SPRING'
    assert normalized['display'] == 'JST SPRING'
    assert normalized['aliases'] == ['JST SPRING']
    assert not term_name_findings(normalized)


def test_default_english_title_case_keeps_shared_small_words_lowercase():
    term = {
        'id': 'data-format', 'kind': 'concept', 'abbreviation': None, 'chinese': '数据格式',
        'english': 'schema of the data', 'display': '旧显示', 'aliases': [], 'components': [],
    }

    normalized = normalize_term_names(term)

    assert normalized['english'] == 'Schema of the Data'
    assert normalized['display'] == '数据格式（Schema of the Data）'


def test_name_case_rules_preserve_code_identifiers_and_explicit_tex_math():
    term = {
        'id': 'implementation-name', 'kind': 'concept', 'abbreviation': r'cpu/\Omega_{i}',
        'abbreviation_case_exception': 0, 'chinese': '实现名称',
        'english': r'$nODe_i$ of get_global_id and ASYNC_FIFO plus \(\Omega_i\)',
        'english_case_exception': 0, 'display': '旧显示', 'aliases': ['get_global_id'],
        'components': [],
    }

    normalized = normalize_term_names(term)

    assert normalized['abbreviation'] == r'CPU/\Omega_{i}'
    assert normalized['english'] == r'$nODe_i$ of get_global_id and ASYNC_FIFO Plus \(\Omega_i\)'
    assert normalized['display'] == r'CPU/\Omega_{i} 实现名称（$nODe_i$ of get_global_id and ASYNC_FIFO Plus \(\Omega_i\)）'
    assert normalized['aliases'] == ['get_global_id']


def test_abbreviation_case_rule_keeps_standalone_tex_commands_exact():
    term = {
        'id': 'omega', 'kind': 'concept', 'abbreviation': r'\Omega',
        'abbreviation_case_exception': 0, 'chinese': '角频率', 'english': 'angular frequency',
        'english_case_exception': 0, 'display': '旧显示', 'aliases': [r'\Omega'], 'components': [],
    }

    normalized = normalize_term_names(term)

    assert normalized['abbreviation'] == r'\Omega'
    assert normalized['english'] == 'Angular Frequency'
    assert normalized['display'] == r'\Omega 角频率（Angular Frequency）'


def test_redundant_abbreviation_is_removed_after_case_and_space_normalization():
    term = {
        'id': 'lux', 'kind': 'unit', 'abbreviation': 'l u x', 'chinese': '勒克斯',
        'english': 'lux', 'display': '旧显示', 'aliases': ['lux', 'Lux', '照度单位'],
        'components': [{'symbol': 'l u x', 'word': 'lux'}],
        'definition': '单位定义保留',
    }

    first, changes = format_term_metadata([term])
    second, second_changes = format_term_metadata(first)

    assert first[0]['abbreviation'] is None
    assert first[0]['components'] == []
    assert first[0]['english'] == 'Lux'
    assert first[0]['display'] == '勒克斯（Lux）'
    assert first[0]['aliases'] == ['Lux', '照度单位']
    assert first[0]['definition'] == term['definition']
    assert changes
    assert second == first
    assert second_changes == []


def test_invalid_flag_is_preserved_and_reported_without_raising():
    term = {
        'id': 'bad', 'kind': 'concept', 'abbreviation': None, 'chinese': '缓存',
        'english': 'cache memory', 'english_case_exception': 2, 'display': '旧显示',
        'aliases': [], 'components': [], 'definition': '定义保持原样',
    }

    normalized, changes = format_term_metadata([term])

    assert normalized[0]['english'] == term['english']
    assert normalized[0]['display'] == '缓存（cache memory）'
    assert normalized[0]['definition'] == term['definition']
    assert any(change['field'] == 'display' for change in changes)
    assert any(finding['field'] == 'english_case_exception'
               for finding in term_name_findings(term))


def test_redundant_abbreviation_with_no_components_is_removed_without_review():
    term = {
        'id': 'unit', 'kind': 'unit', 'abbreviation': 'lx',
        'abbreviation_case_exception': 0, 'chinese': '单位名',
        'english': 'l x', 'english_case_exception': 0,
        'display': '旧显示', 'aliases': ['lx'], 'components': [],
    }

    formatted, changes = format_term_metadata([term])

    assert formatted[0]['abbreviation'] is None
    assert formatted[0]['components'] == []
    assert formatted[0]['display'] == '单位名（L X）'
    assert not term_name_findings(formatted[0])
    assert changes


def test_safe_name_formatting_runs_while_component_and_source_issues_remain():
    term = {
        'id': 'jst-spring', 'kind': 'official_name', 'abbreviation': 'js',
        'abbreviation_case_exception': 0, 'chinese': '制度名',
        'english': 'jst spring', 'english_case_exception': 0,
        'display': '旧显示', 'aliases': ['jst spring', 'js'],
        'components': [{'symbol': 'x', 'word': 'unknown'}],
        'official_spelling': 'jst spring', 'case_source': None,
        'definition': '定义原样保留', 'explanation': '解释原样保留',
    }
    before = copy.deepcopy(term)

    formatted, changes = format_term_metadata([term])

    assert term == before
    assert formatted[0]['english'] == 'Jst Spring'
    assert formatted[0]['official_spelling'] == 'Jst Spring'
    assert formatted[0]['abbreviation'] == 'JS'
    assert formatted[0]['display'] == 'JS 制度名（Jst Spring）'
    assert formatted[0]['aliases'] == ['Jst Spring', 'JS']
    assert formatted[0]['components'] == before['components']
    assert formatted[0]['definition'] == before['definition']
    assert formatted[0]['explanation'] == before['explanation']
    assert {'english', 'official_spelling', 'abbreviation', 'display'} <= {
        change['field'] for change in changes
    }
    assert {finding['field'] for finding in term_name_findings(formatted[0])} == {
        'components', 'case_source'
    }

    repaired, repair_changes, errors = repair_batches.format_document_terms(
        {'appendix': {'terms': [term]}}, include_legacy=True
    )

    assert repaired['appendix']['terms'][0]['display'] == formatted[0]['display']
    assert repair_changes
    assert any('components' in error for error in errors)
    assert any('case_source' in error for error in errors)


def test_saved_schema_accepts_old_terms_while_new_writer_requires_both_flags():
    old_term = {
        'abbreviation': None, 'chinese': '缓存', 'english': 'Cache',
        'professional_definition': {'genus': '缓存', 'differentia': '提供较近访问', 'boundary': '不保证永久有效', 'extension': None},
        'intuitive_explanation': {'anchor': '工具托盘', 'mapping': '常用工具放在近处', 'intuition': '读取更快', 'extension': None},
        'typical_example': {'initial_conditions': '程序第二次读取', 'mechanism': '读取已保存副本', 'outcome': '省去重复计算', 'extension': None},
        'id': 'cache', 'aliases': ['Cache'], 'kind': 'concept', 'components': [],
        'official_spelling': None, 'case_source': None,
    }
    stored_term_schema = contract.schema('c-unit')['properties']['appendix']['properties']['terms']['items']
    writer_term_schema = contract.writer_schema({})['properties']['appendix']['properties']['terms']['items']

    assert stored_term_schema['properties']['abbreviation_case_exception']['default'] == 0
    assert stored_term_schema['properties']['english_case_exception']['default'] == 0
    assert 'abbreviation_case_exception' not in stored_term_schema['required']
    assert 'english_case_exception' not in stored_term_schema['required']
    assert Draft202012Validator(stored_term_schema).is_valid(old_term)
    assert not Draft202012Validator(writer_term_schema).is_valid(old_term)
    legacy_nulls = copy.deepcopy(old_term)
    legacy_nulls.update(abbreviation_case_exception=None, english_case_exception=None)
    assert Draft202012Validator(stored_term_schema).is_valid(legacy_nulls)
    assert not Draft202012Validator(writer_term_schema).is_valid(legacy_nulls)
    new_term = copy.deepcopy(old_term)
    new_term.update(abbreviation_case_exception=0, english_case_exception=0)
    assert Draft202012Validator(writer_term_schema).is_valid(new_term)
    prompt_rules = ' '.join(contract.glossary_rules())
    assert 'abbreviation_case_exception' in prompt_rules
    assert 'english_case_exception' in prompt_rules


def test_case_findings_join_existing_unit_repair_findings():
    term = {
        'abbreviation': 'cpu', 'abbreviation_case_exception': 0,
        'chinese': '中央处理器', 'english': 'central processing unit',
        'english_case_exception': 0,
        'professional_definition': {'genus': '设备中的处理单元', 'differentia': '执行指令', 'boundary': '不负责保存长期数据', 'extension': None},
        'intuitive_explanation': {'anchor': '工作台', 'mapping': '负责处理送来的任务', 'intuition': '逐条完成操作', 'extension': None},
        'typical_example': {'initial_conditions': '程序收到一条指令', 'mechanism': '处理单元执行指令', 'outcome': '程序得到计算结果', 'extension': None},
        'id': 'cpu', 'aliases': ['cpu'], 'kind': 'initialism',
        'components': [{'symbol': 'c', 'word': 'central'}, {'symbol': 'p', 'word': 'processing'}, {'symbol': 'u', 'word': 'unit'}],
        'official_spelling': None, 'case_source': None,
    }
    value = {
        'question_id': 'q1',
        'plan': {'items': [{'id': 'p1', 'statement': '说明处理单元', 'resource_ids': ['r1']}]},
        'premise': '程序怎样执行指令？',
        'explanation': [{'id': 'g1', 'title_premise': '程序处理指令', 'title_question': '由谁执行？',
                        'claim': '处理单元执行指令', 'reasoning': '程序将指令交给处理单元',
                        'grounding': '一条指令得到计算结果', 'supplement': None,
                        'resource_ids': ['r1'], 'plan_ids': ['p1'], 'resources': []}],
        'result': {'answer': '处理单元执行指令', 'generalization': '程序按处理流程执行任务'},
        'appendix': {'pitfalls': [], 'quiz': [], 'terms': [term], 'local_notations': []},
    }
    resources = [{'id': 'r1', 'source_id': 'source-1', 'kind': 'text', 'original': 'CPU processes instructions', 'question_ids': ['q1']}]

    findings = writing_checks.unit_findings(value, resources, {}, 'q1')

    assert any(finding['rule'] == 'term_name' and finding['path'].startswith('/appendix/terms/0/')
               for finding in findings)


def test_repair_batch_formats_flagged_terms_and_leaves_missing_flag_history_untouched():
    legacy = {
        'id': 'old', 'kind': 'concept', 'abbreviation': None, 'chinese': '缓存',
        'english': 'cache memory', 'display': '旧显示', 'aliases': [], 'components': [],
    }
    flagged = {
        'id': 'new', 'kind': 'concept', 'abbreviation': None, 'chinese': '数据格式',
        'english': 'schema of the data', 'english_case_exception': 0,
        'abbreviation_case_exception': 0, 'display': '旧显示', 'aliases': [], 'components': [],
    }
    nullable_legacy = {
        'id': 'nullable', 'kind': 'concept', 'abbreviation': None, 'chinese': 'Cache Memory',
        'english': 'Cache Memory', 'english_case_exception': None,
        'abbreviation_case_exception': None, 'display': 'Cache Memory（Cache Memory）',
        'aliases': ['Cache Memory', 'cache memory'], 'components': [],
    }
    document = {'appendix': {'terms': [legacy, flagged, nullable_legacy]}}

    repaired, changes, errors = repair_batches.format_document_terms(document)

    assert errors == []
    assert repaired['appendix']['terms'][0] == legacy
    assert repaired['appendix']['terms'][1]['english'] == 'Schema of the Data'
    assert repaired['appendix']['terms'][1]['display'] == '数据格式（Schema of the Data）'
    assert repaired['appendix']['terms'][2]['display'] == 'Cache Memory'
    assert repaired['appendix']['terms'][2]['aliases'] == ['Cache Memory']
    assert {change['term_index'] for change in changes} == {1, 2}
    again, again_changes, again_errors = repair_batches.format_document_terms(repaired)
    assert again == repaired
    assert again_changes == []
    assert again_errors == []


def test_null_exception_bits_use_default_rules_and_missing_bits_remain_compatible():
    legacy = {
        'id': 'old', 'kind': 'concept', 'abbreviation': None, 'chinese': 'Cache Memory',
        'english': 'Cache Memory', 'display': 'Cache Memory',
        'aliases': ['Cache Memory'], 'components': [],
    }
    assert not term_name_findings(legacy)

    explicit_null = copy.deepcopy(legacy)
    explicit_null.update(abbreviation_case_exception=None, english_case_exception=None,
                         display='Cache Memory（Cache Memory）',
                         aliases=['Cache Memory', 'cache memory'])
    normalized, changes = format_term_metadata([explicit_null])

    assert normalized[0]['english'] == 'Cache Memory'
    assert normalized[0]['display'] == 'Cache Memory'
    assert normalized[0]['aliases'] == ['Cache Memory']
    assert changes
    assert not term_name_findings(normalized[0])


def test_migration_proposes_safe_name_patch_while_recording_unresolved_fields():
    term = {
        'id': 'jst-spring', 'kind': 'official_name', 'abbreviation': 'js',
        'abbreviation_case_exception': 0, 'chinese': '制度名',
        'english': 'jst spring', 'english_case_exception': 0,
        'display': '旧显示', 'aliases': ['jst spring', 'js'],
        'components': [{'symbol': 'x', 'word': 'unknown'}],
        'official_spelling': 'jst spring', 'case_source': None,
        'definition': '定义保留', 'explanation': '解释保留',
    }

    proposal = migrate_term_names.propose_term_migration(
        {'appendix': {'terms': [term]}}, 'source-hash'
    )

    assert len(proposal['patches']) == 1
    patch = proposal['patches'][0]
    assert patch['after']['english'] == 'Jst Spring'
    assert patch['after']['official_spelling'] == 'Jst Spring'
    assert patch['after']['abbreviation'] == 'JS'
    assert patch['after']['display'] == 'JS 制度名（Jst Spring）'
    assert 'components' not in patch['after']
    assert 'definition' not in patch['after'] and 'explanation' not in patch['after']
    record = proposal['records'][0]
    assert record['status'] == 'proposed'
    assert {finding['field'] for finding in record['findings']} == {'components', 'case_source'}


def test_single_file_apply_helper_checks_hash_and_preserves_non_name_content(tmp_path):
    term = {
        'id': 'spring', 'kind': 'concept', 'abbreviation': None,
        'chinese': 'JST SPRING', 'english': 'JST SPRING',
        'display': 'JST SPRING（JST SPRING）', 'aliases': [],
        'components': [], 'definition': '定义和解释都保留。',
        'explanation': ['解释也保留。'],
    }
    document = {'appendix': {'terms': [term]}}
    source = tmp_path / 'source.json'
    proposal_path = tmp_path / 'proposal.json'
    output = tmp_path / 'copy.json'
    source.write_text(json.dumps(document, ensure_ascii=False), encoding='utf-8')
    source_bytes = source.read_bytes()
    proposal = migrate_term_names.propose_term_migration(
        document, __import__('hashlib').sha256(source_bytes).hexdigest()
    )
    proposal_path.write_text(json.dumps(proposal, ensure_ascii=False), encoding='utf-8')

    result = migrate_term_names.apply_proposal_file(source, proposal_path, output)

    assert source.read_bytes() == source_bytes
    copied = json.loads(output.read_text(encoding='utf-8'))
    copied_term = copied['appendix']['terms'][0]
    assert copied_term['display'] == 'JST SPRING'
    assert copied_term['english'] == 'Jst Spring'
    assert copied_term['definition'] == term['definition']
    assert copied_term['explanation'] == term['explanation']
    assert result['source_modified'] is False

    source.write_bytes(source_bytes + b' ')
    with pytest.raises(ValueError, match='哈希已改变'):
        migrate_term_names.apply_proposal_file(source, proposal_path, tmp_path / 'stale-copy.json')


def test_term_migration_emits_name_only_patch_without_changing_input(tmp_path, monkeypatch):
    term = {
        'id': 'spring', 'kind': 'concept', 'abbreviation': None,
        'chinese': 'JST SPRING', 'english': 'JST SPRING',
        'display': 'JST SPRING（JST SPRING）', 'aliases': [], 'components': [],
        'definition': '定义和解释都保留。', 'explanation': ['解释也保留。'],
    }
    document = {'appendix': {'terms': [term]}}
    before = copy.deepcopy(document)

    proposal = migrate_term_names.propose_term_migration(document, 'test-hash')

    assert document == before
    assert proposal['source_sha256'] == 'test-hash'
    assert len(proposal['patches']) == 1
    patch = proposal['patches'][0]
    assert patch['path'] == '/appendix/terms/0'
    assert patch['after']['display'] == 'JST SPRING'
    assert patch['after']['english'] == 'Jst Spring'
    assert 'definition' not in patch['after'] and 'explanation' not in patch['after']
    assert proposal['records'][0]['status'] == 'proposed'

    source = tmp_path / 'book.json'
    output = tmp_path / 'migration-proposal.json'
    source.write_text(json.dumps(before, ensure_ascii=False), encoding='utf-8')
    original_bytes = source.read_bytes()
    monkeypatch.setattr(sys, 'argv', ['migrate_term_names.py', '--input', str(source), '--output', str(output)])

    migrate_term_names._main()

    assert source.read_bytes() == original_bytes
    saved = json.loads(output.read_text(encoding='utf-8'))
    assert saved['format'] == 'lessonweave-term-name-migration-v1'
    assert saved['source_sha256']
    assert saved['patches'][0]['after']['display'] == 'JST SPRING'
