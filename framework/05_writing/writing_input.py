"""大输入改为同一次 C 调用读取完整本地材料，原件与材料分配不截断"""
import copy
import json
from pathlib import Path
import sys
from functools import lru_cache


@lru_cache(maxsize=8)
def context_window(model):
    import os
    for base in [Path(os.environ.get('CODEX_HOME',Path.home()/'.codex'))]:
        path=base/'models_cache.json'
        if path.is_file():
            for entry in json.loads(path.read_text('utf-8')).get('models',[]):
                if entry.get('slug')==model:
                    return int(entry['context_window'])*entry.get('effective_context_window_percent',95)//100
    return None


def prepare(root,folder,qid,prompt,model):
    window=context_window(model)
    # 本机接口实际回执给出的字符上限；这只决定传输方式，不裁剪材料
    transport_limit=1048576
    transport_fit=len(prompt)+8192<transport_limit
    if transport_fit and (window is None or len(prompt.encode('utf-8')) < window*3//4):
        return prompt,False,{'mode':'inline','context_window':window}
    count=None
    if transport_fit:
        import tiktoken
        count=len(tiktoken.get_encoding('o200k_base').encode(prompt,disallowed_special=()))
    if transport_fit and (window is None or count < window*3//4):
        return prompt,False,{'mode':'inline','context_window':window,'estimated_payload_tokens':count}
    payload=json.loads(prompt)
    field='materials'if 'materials'in payload else'material_pool'
    complete=payload[field]
    path=Path(folder)/('complete-materials-'+qid+'.json')
    path.write_text(json.dumps(complete,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    view=[]
    values=complete.items()if isinstance(complete,dict)else[(None,r)for r in complete]
    for key,resource in values:
        row={k:copy.deepcopy(resource[k])for k in ['id','kind','source_id','resource_ids','scope','asset','model_asset','source_path','start_line','end_line']if k in resource}
        if 'original'in resource:
            row.update(characters=len(resource['original']),
                       lines=len(resource['original'].splitlines()))
        view.append((key,row))
    payload[field]=dict(view)if isinstance(complete,dict)else[row for _,row in view]
    reader=Path(__file__).resolve()
    import shlex
    arguments=[sys.executable,str(reader),str(path)]
    command=('& '+' '.join("'"+arg.replace("'","''")+"'"for arg in arguments))if sys.platform=='win32'else shlex.join(arguments)
    payload['complete_material_reader']={'file':str(path),'command':command,
        'operations':'list；get 材料键；lines 材料键 起始行 结束行；find 正则；lines 以当前材料片段的第一行为 1，索引中的 start_line 与 end_line 只用于定位原文件',
        'rules':'本次先读取本问完整材料，再按职责规划和写作；大源码可用检索和明确行范围阅读，不能把清单当成已经读过内容；来源编号和全部原文仍完整保留，不调用其他模型，不改文件，不联网'}
    return json.dumps(payload,ensure_ascii=False,separators=(',',':')),True,{
        'mode':'complete_local_materials','context_window':window,'transport_character_limit':transport_limit,'estimated_payload_tokens':count,
        'complete_text_file':str(path),'materials':len(view)}


def main():
    import re
    data=json.loads(Path(sys.argv[1]).read_text('utf-8'));command=sys.argv[2]
    byid=data if isinstance(data,dict)else{row['id']:row for row in data}
    if command=='list':
        for key,row in byid.items():print(json.dumps({k:v for k,v in row.items()if k!='original'}|{'lookup_key':key,'characters':len(row.get('original',''))},ensure_ascii=False))
    elif command=='get':print(json.dumps(byid[sys.argv[3]],ensure_ascii=False))
    elif command=='lines':
        row=byid[sys.argv[3]];start=int(sys.argv[4]);end=int(sys.argv[5])
        for i,line in enumerate(row.get('original','').splitlines(),1):
            if start<=i<=end:print(f'{i}: {line}')
    elif command=='find':
        pattern=re.compile(sys.argv[3])
        for key,row in byid.items():
            for i,line in enumerate(row.get('original','').splitlines(),1):
                if pattern.search(line):print(json.dumps({'id':row['id'],'lookup_key':key,'line':i,'text':line},ensure_ascii=False))


if __name__=='__main__':main()
