"""按真实节点读取完整材料，文件和节点均不设置截断上限"""
import argparse
import json
from pathlib import Path
import re
from source_disposition import walk, text_of, source_of


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('material', type=Path)
    parser.add_argument('action', choices=['list', 'get', 'subtree', 'find', 'file'])
    parser.add_argument('value', nargs='?')
    args = parser.parse_args()
    material = json.loads(args.material.read_text(encoding='utf-8'))
    tree = material.get('tree', material)
    nodes = {n['id']: n for n in walk(tree)}
    if args.action == 'find':
        value = [{'id': n['id'], 'type': n['type'], 'text': text_of(n), 'source': n.get('source')}
                 for n in nodes.values() if re.search(args.value, text_of(n), re.I)]
    elif args.action == 'file':
        base = material.get('repository') or material.get('original', {}).get('repository')
        original = Path(base) if base else args.material.parent
        path = (original / args.value).resolve()
        if not path.is_relative_to(original.resolve()):
            raise ValueError('只读取当前材料原件目录中的文件')
        print(path.read_text(encoding='utf-8', errors='replace'))
        return
    else:
        node = nodes[args.value] if args.value else tree
        if args.action == 'list':
            value = [{'id': n['id'], 'type': n['type'], 'text': text_of(n), 'children': len(n.get('children', [])), 'source': source_of(n)}
                     for n in node.get('children', [])]
        elif args.action == 'get':
            value = {**node, 'children': [n['id'] for n in node.get('children', [])]}
        else:
            value = node
    print(json.dumps(value, ensure_ascii=False, separators=(',', ':')))


if __name__ == '__main__':
    main()
