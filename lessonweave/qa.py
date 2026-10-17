from pathlib import Path
import json
from .agents import Backend
from .storage import read


def answer(root, payload):
    from . import legacy as flow
    book = read(root/'05_writing/preview-book.json', read(root/'05_writing/book.json'))
    entries = [section for chapter in book['chapters'] for section in chapter['sections']]
    selected = next((entry for entry in entries if entry['id']==payload.get('section_id')), entries[0])
    doc = read(root/selected['path'])
    pack = read(root/doc['grounding']['source_pack_path'])
    prompt = '围绕读者所选内容回答问题，先按实际材料解释，补充推断时明确条件，保留数值和来源 ID，只用本次材料，不执行工具\n'+json.dumps({'question':payload['question'],'selection':payload.get('selection'),'chapter':doc,'source_pack':flow.runtime.source_view(pack)},ensure_ascii=False)
    schema = flow.generation.obj({'answer':flow.generation.STRING,'source_ids':flow.generation.STRINGS})
    result = Backend(root, role='reader_qa').call('reader-qa-'+__import__('uuid').uuid4().hex, prompt, schema, pack.get('images'))
    return {'status':'completed','answer':result['answer'],'source_ids':result['source_ids']}
