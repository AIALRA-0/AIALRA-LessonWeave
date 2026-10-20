"""让每个问题从固定公共背景独立写作，再由另一上下文核对材料与连贯性"""
import argparse
import concurrent.futures
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from teaching_coverage import evaluate, read, review_document, save, teaching_blocks

STAGE = Path(__file__).resolve().parent


def obj(properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}


STRING = {'type': 'string'}
STRINGS = {'type': 'array', 'items': STRING}
BOOL = {'type': 'boolean'}
PARAGRAPH = obj({'id': STRING, 'kind': {'const': 'paragraph'}, 'text': STRING})
BLOCK = {'anyOf': [PARAGRAPH,
    obj({'id': STRING, 'kind': {'const': 'list'}, 'lead_in': STRING, 'items': STRINGS}),
    obj({'id': STRING, 'kind': {'const': 'table'}, 'headers': STRINGS, 'rows': {'type': 'array', 'items': STRINGS}}),
    obj({'id': STRING, 'kind': {'const': 'image'}, 'asset': STRING, 'caption': STRING, 'source_id': STRING}),
    obj({'id': STRING, 'kind': {'const': 'image'}, 'asset': STRING, 'caption': STRING,
         'source_id': STRING, 'source_region': STRING})]}
BINDING = obj({'point_id': STRING, 'block_ids': STRINGS, 'explanation': STRING})
UNIT = obj({'question_id': STRING, 'problem': PARAGRAPH,
            'explanation': {'type': 'array', 'items': BLOCK}, 'synthesis': PARAGRAPH,
            'summary': PARAGRAPH, 'bindings': {'type': 'array', 'items': BINDING}})
WRITER_SCHEMA = obj({'status': {'enum': ['ready', 'completed']}, 'unit': {'anyOf': [UNIT, {'type': 'null'}]}})
VERDICT = obj({'passed': BOOL, 'reason': STRING})
REVIEW_SCHEMA = obj({
    'inventory_complete': VERDICT, 'coherence': VERDICT, 'pitfalls': VERDICT,
    'quiz': VERDICT, 'terminology': VERDICT, 'writing_style': VERDICT,
    'unit_reviews': {'type': 'array', 'items': obj({'question_id': STRING, 'passed': BOOL, 'reason': STRING})},
    'points': {'type': 'array', 'items': obj({'point_id': STRING, 'passed': BOOL, 'block_ids': STRINGS, 'reason': STRING})},
})

