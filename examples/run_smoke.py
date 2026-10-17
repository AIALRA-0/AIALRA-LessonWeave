"""从三个独立输入启动正式流水线，运行资料保存到站点数据目录"""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from lessonweave.storage import Store, read, save
from lessonweave.pipeline import scaffold, run


def one(kind):
    store = Store()
    root = store.root/'projects'/('demo-'+kind)
    scaffold(root)
    payload = read(Path(__file__).parent/(kind+'.input.json'))
    if payload['kind'] != 'url':
        payload['material'] = str((Path(__file__).parent/payload['material']).resolve())
    save(root/'00_source/input.json',payload)
    store.register('demo-'+kind,{'web':'展品借展怎样控制光照','pdf':'怎样解释两次鸟类观察','code':'温度报表怎样处理数据'}[kind],root)
    result = run(root,3)
    print(json.dumps({'project':kind,**result},ensure_ascii=False),flush=True)
    return result


if __name__=='__main__':
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(one,['web','pdf','code']))
    save(Store().root/'smoke-results.json',results)
