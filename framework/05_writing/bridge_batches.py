"""承接只读取已完成答案，按已选批量并行生成，保持每节独立归属"""
import concurrent.futures as futures
from lessonweave.concurrency import options
import lean_contract as contract


def generate(backend, boundaries):
    config = options()
    size = config['bridge_batch_sections'] or max(1, len(boundaries))
    groups = [boundaries[i:i + size] for i in range(0, len(boundaries), size)]
    def call(pair):
        index, rows = pair
        name = 'c_bridges' if len(groups) == 1 else 'c_bridges-batch-' + str(index + 1).zfill(3)
        prompt = contract.dumps({'task': '为各节写两段承接，carryover 承上，premise 加 question 启下，标题固定为承上启下',
            'rules': ['只根据实际答案承上，首节根据材料情境起笔，前提直接引出问题，不重述整节内容，不生成术语或审查'],
            'boundaries': rows})
        return index, backend._call_once(name, prompt, contract.schema('c-bridges'))
    output = {}
    records = []
    with futures.ThreadPoolExecutor(max_workers=config['bridge_calls']) as pool:
        pending = {pool.submit(call, pair): pair[0] for pair in enumerate(groups)}
        for future in futures.as_completed(pending):
            index = pending[future]
            try:
                _, value = future.result()
                output[index] = value['bridges']
                records.append({'batch': index + 1, 'sections': len(value['bridges']), 'status': 'completed'})
            except Exception as error:
                records.append({'batch': index + 1, 'status': 'recorded_error', 'error': str(error)})
    return {'bridges': [row for index in sorted(output) for row in output[index]], 'records': records}
