"""完整正文覆盖 OCR 残片时，只保留一个可独立翻译的文本版本。"""

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'framework' / '05_writing'))

import book_sources


def test_source_text_fragments_covered_by_complete_text_stay_as_provenance():
    node = {
        'source': {'path': 'paper.pdf', 'page': 1, 'bbox': [0, 0, 100, 100]},
        'content': {
            'text': ('The construction is one-dimensional and normal. It admits a fundamental '
                     'system of locally pseudoconvex neighborhoods. Ohsawa–Takegoshi and Ueda’s results apply.'),
            'source_text': [
                {'text': 'one-', 'source': {'page': 1, 'bbox': [0, 0, 10, 10]}},
                {'text': 'nor-', 'source': {'page': 1, 'bbox': [0, 10, 10, 20]}},
                {'text': 'admits a fundamental system of locally pseu-',
                 'source': {'page': 1, 'bbox': [0, 20, 10, 30]}},
                {'text': 'Ohsawa–Takegoshi', 'source': {'page': 1, 'bbox': [0, 30, 10, 40]}},
                {'text': 'Ueda’s', 'source': {'page': 1, 'bbox': [0, 40, 10, 50]}},
                {'text': 'Additional hypothesis', 'source': {'page': 1, 'bbox': [0, 50, 10, 60]}},
            ],
        },
    }
    for fragment in node['content']['source_text']:
        fragment['source']['path'] = 'paper.pdf'
    original = copy.deepcopy(node)

    texts = book_sources._texts(node)
    entries, original_text_count = book_sources._text_entries(node)
    sentences = [sentence for text, original_index in entries
                 for sentence in book_sources._sentences(f'n000005.text{original_index}', text)]

    assert texts == [node['content']['text'], 'Additional hypothesis']
    assert entries == [(node['content']['text'], 1), ('Additional hypothesis', 7)]
    assert original_text_count == 7
    assert [row['original'] for row in sentences] == [
        'The construction is one-dimensional and normal.',
        'It admits a fundamental system of locally pseudoconvex neighborhoods.',
        'Ohsawa–Takegoshi and Ueda’s results apply.',
        'Additional hypothesis',
    ]
    assert [row['id'] for row in sentences] == [
        'n000005.text1.s1', 'n000005.text1.s2', 'n000005.text1.s3', 'n000005.text7.s1',
    ]
    assert node == original
    assert node['content']['source_text'] == original['content']['source_text']


def test_source_text_not_covered_by_full_text_remains_independent():
    node = {'content': {'text': 'The abstract is complete.',
                        'source_text': [{'text': 'A separate appendix note.'}]}}

    assert book_sources._texts(node) == ['The abstract is complete.', 'A separate appendix note.']


def test_hyphen_prefix_only_matches_a_continuing_word_and_context():
    assert book_sources._source_fragment_covered('one-', 'one-dimensional geometry')
    assert book_sources._source_fragment_covered(
        'admits a fundamental system of locally pseu-',
        'It admits a fundamental system of locally pseudoconvex neighborhoods.')
    assert not book_sources._source_fragment_covered('one-', 'one quantity is present')
    assert not book_sources._source_fragment_covered('locally pseu-', 'A different locally convex result.')


def test_same_words_on_a_different_page_or_region_are_not_hidden():
    node = {'source': [{'path': 'paper.pdf', 'page': 1, 'bbox': [0, 0, 100, 100]}],
            'content': {'text': 'A one-dimensional example.', 'source_text': []}}
    for page, bbox in [(2, [0, 0, 10, 10]), (1, [200, 200, 210, 210])]:
        node['content']['source_text'] = [{'text': 'one-', 'source': {'path': 'paper.pdf', 'page': page, 'bbox': bbox}}]
        assert book_sources._texts(node) == ['A one-dimensional example.', 'one-']
