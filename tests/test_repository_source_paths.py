"""新获取的 ZIP 可以保存在任意批次目录，材料读取按实际登记路径定位源码"""
from lessonweave import legacy
from lessonweave.storage import save
import book_sources


def test_repository_fragments_follow_registered_acquisition_directory(tmp_path):
    repo=tmp_path/'00_source/materials/source-0001/repository';repo.mkdir(parents=True)
    file=repo/'core.v';file.write_bytes(b'module core; endmodule\n')
    save(tmp_path/'00_source/source.json',{'repository':repo.relative_to(tmp_path).as_posix()})
    node={'id':'n1','source':[{'kind':'code','path':file.relative_to(tmp_path).as_posix()}],'content':{'role':'source'}}
    fragments=book_sources._file_fragments(tmp_path,node)
    assert len(fragments)==1 and fragments[0]['text']=='module core; endmodule\n'
