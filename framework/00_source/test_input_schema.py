"""在任意项目的材料目录中检查 input.json，失败时保留具体字段位置"""
from pathlib import Path
import json
import jsonschema


def test_input_matches_schema():
    # 检查四个必填字段、非空字符串、kind 与 mode 的选项及额外字段
    folder=Path(__file__).resolve().parent
    schema=json.loads((folder/'input.schema.json').read_text('utf-8'))
    payload=json.loads((folder/'input.json').read_text('utf-8'))
    jsonschema.Draft202012Validator(schema).validate(payload)
