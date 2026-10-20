"""优先读取标准 JSON，只自动补齐已经生成内容中的引号转义"""
import json
import time
from lessonweave.storage import save


def decode(content,folder):
    try:return json.loads(content)
    except json.JSONDecodeError as original:
        from json_repair import repair_json
        started=time.perf_counter()
        value=repair_json(content,return_objects=True,ensure_ascii=False,skip_json_loads=True)
        canonical=json.dumps(value,ensure_ascii=False,separators=(',',':'))
        # 两边的原字符必须完全一致，只允许 JSON 引号的转义方式不同
        if content.strip().replace('\\"','"')!=canonical.replace('\\"','"'):
            raise original
        save(folder/'json-format-repair.json',{'method':'quote_escape_only','characters_preserved':True,
            'seconds':time.perf_counter()-started,'model_calls':0})
        return value
