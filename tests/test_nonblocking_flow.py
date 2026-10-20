"""检查真实父子来源、问题记录和请求恢复，测试不调用模型"""
import concurrent.futures
import copy
from lessonweave import pipeline
from lessonweave.storage import read
import information_points


def test_figure_inherits_real_child_image_evidence():
    # 图容器通过真实子图获得出处，空容器无需伪造一份引文
    rows=[{'source_id':'figure','content':{'source_text':[]},'child_source_ids':['image'],'evidence_kind':'content'},
          {'source_id':'image','content':{'asset':'/00_source/chart.webp'}}]
    point={'id':'p1','description':'图表趋势','checks':['解释实际趋势'],'source_ids':['image','figure'],
           'source_refs':[{'source_id':'image','quote':'/00_source/chart.webp','region':'全图'}]}
    before=copy.deepcopy(point); findings=[]
    information_points.validate({'points':[point]},rows,findings=findings)
    assert findings==[] and point==before


def test_unresolved_quote_is_recorded_without_dropping_the_point():
    # 无法匹配的引文保留待修记录，信息点及其原始检查要求继续进入后续流程
    rows=[{'source_id':'n1','content':{'text':'容量为 16 MB'}}]
    point={'id':'p1','description':'容量','checks':['解释 16 MB'],'source_ids':['n1'],
           'source_refs':[{'source_id':'n1','quote':'32 MB','region':'text'}]}
    candidate={'points':[point]}; findings=[]
    assert information_points.validate(candidate,rows,findings=findings) is candidate
    assert findings and candidate['points']==[point]


def test_quality_finding_does_not_discard_generated_candidate(tmp_path):
    # 检查器报告问题后，调用方仍取得已经生成的候选内容，并能读取具体问题
    class Backend:
        root=tmp_path
        def call(self,*args):return {'points':[{'id':'p1'}]}
    def inspect(value):raise ValueError('需要核对来源对应')
    result=pipeline.stage_call(Backend(),'inventory-test','test',{},inspect)
    assert result=={'points':[{'id':'p1'}]}
    assert read(tmp_path/'runtime/findings.json')['items'][0]['message']=='需要核对来源对应'


def test_parallel_recovery_keeps_completed_siblings(tmp_path):
    # 恢复只重做尚未完成的任务，已完成任务不会再次调用
    calls={1:0,2:0,3:0}
    def work(value):
        calls[value]+=1
        if value==1 and calls[value]==1:raise OSError('连接暂时中断')
        return value
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        assert sorted(pipeline.collect(pool,[1,2,3],work,tmp_path))==[1,2,3]
    assert calls=={1:2,2:1,3:1}
    assert read(tmp_path/'runtime/findings.json')['items'][0]['behavior']=='repair'
