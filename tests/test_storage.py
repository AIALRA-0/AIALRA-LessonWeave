"""瞬时文件占用只重试保存动作，模型任务不随之再次执行"""
import os
import pytest
from lessonweave import storage


@pytest.mark.skipif(os.name!='nt',reason='只验证 Windows 的文件占用错误')
def test_transient_windows_replace_retries_without_losing_json(tmp_path,monkeypatch):
    replace=storage.os.replace;attempts=[]
    def occupied(first,second):
        attempts.append(1)
        if len(attempts)<3:
            error=PermissionError('文件暂时被占用');error.winerror=5;raise error
        return replace(first,second)
    monkeypatch.setattr(storage.os,'replace',occupied)
    path=tmp_path/'state.json';value={'内容':'全部保存','requests':17}
    storage.save(path,value)
    assert len(attempts)==3 and storage.read(path)==value


def test_unrelated_replace_failure_is_not_retried(tmp_path,monkeypatch):
    attempts=[]
    def denied(first,second):
        attempts.append(1)
        error=PermissionError('其他访问错误');error.winerror=2;raise error
    monkeypatch.setattr(storage.os,'replace',denied)
    with pytest.raises(PermissionError):storage.save(tmp_path/'state.json',{'x':1})
    assert len(attempts)==1
