"""术语大小写位、统一整理与旧读本兼容"""
import copy
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'framework' / '05_writing'))

import lean_contract as contract
from book_terminology import format_term_metadata, normalize_term_names, term_name_findings
import independent_checks as writing_checks
import repair_batches


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


def test_default_english_title_case_keeps_shared_small_words_lowercase():
    term = {
        'id': 'data-format', 'kind': 'concept', 'abbreviation': None, 'chinese': '数据格式',
        'english': 'schema of the data', 'display': '旧显示', 'aliases': [], 'components': [],
    }

    normalized = normalize_term_names(term)

    assert normalized['english'] == 'Schema of the Data'
    assert normalized['display'] == '数据格式（Schema of the Data）'


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

    assert normalized == [term]
    assert changes == []
    assert term_name_findings(term) == [
        {'field': 'english_case_exception', 'message': '大小写例外位只能是整数 0 或 1'}
    ]


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


def test_repair_batch_formats_flagged_terms_and_leaves_legacy_terms_untouched():
    legacy = {
        'id': 'old', 'kind': 'concept', 'abbreviation': None, 'chinese': '缓存',
        'english': 'cache memory', 'display': '旧显示', 'aliases': [], 'components': [],
    }
    flagged = {
        'id': 'new', 'kind': 'concept', 'abbreviation': None, 'chinese': '数据格式',
        'english': 'schema of the data', 'english_case_exception': 0,
        'abbreviation_case_exception': 0, 'display': '旧显示', 'aliases': [], 'components': [],
    }
    document = {'appendix': {'terms': [legacy, flagged]}}

    repaired, changes, errors = repair_batches.format_document_terms(document)

    assert errors == []
    assert repaired['appendix']['terms'][0] == legacy
    assert repaired['appendix']['terms'][1]['english'] == 'Schema of the Data'
    assert repaired['appendix']['terms'][1]['display'] == '数据格式（Schema of the Data）'
    assert changes and all(change['term_index'] == 1 for change in changes)
    again, again_changes, again_errors = repair_batches.format_document_terms(repaired)
    assert again == repaired
    assert again_changes == []
    assert again_errors == []
