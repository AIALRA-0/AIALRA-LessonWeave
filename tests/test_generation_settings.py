"""核对角色默认值、项目保存、真实任务参数与输入检查，全程使用本地替身"""
from pathlib import Path
import json
import pytest
from lessonweave import generation_settings as config
from lessonweave.agents import Backend


@pytest.fixture(autouse=True)
def clear_settings_environment(monkeypatch):
    for name in ['LESSONWEAVE_MODEL','LESSONWEAVE_EFFORT','LESSONWEAVE_GENERATION_MODEL',
                 'LESSONWEAVE_GENERATION_EFFORT','LESSONWEAVE_TRANSLATION_MODEL','LESSONWEAVE_TRANSLATION_EFFORT']:
        monkeypatch.delenv(name,raising=False)
    monkeypatch.setenv('LESSONWEAVE_BACKEND','codex')


def test_defaults_separate_generation_from_translation(tmp_path):
    assert config.for_role(tmp_path,'lean_writing') == {'model':'gpt-6.1-sol','effort':'high'}
    assert config.for_role(tmp_path,'lean_translation') == {'model':'deepseek-flash','effort':'off'}


def test_project_choice_reaches_backend_and_keeps_other_projects_independent(tmp_path):
    value={'generation':{'model':'gpt-6-luna','effort':'max'},'translation':{'model':'gpt-6.1-sol','effort':'medium'}}
    config.update(tmp_path,value)
    writer=Backend(tmp_path,role='lean_writing')
    translator=Backend(tmp_path,role='lean_translation')
    assert (writer.model,writer.effort)==('gpt-6-luna','max')
    assert (translator.model,translator.effort)==('gpt-6.1-sol','medium')
    assert config.load(tmp_path/'different-project')==config.DEFAULTS


def test_explicit_project_values_override_server_defaults(tmp_path,monkeypatch):
    monkeypatch.setenv('LESSONWEAVE_MODEL','server-model')
    monkeypatch.setenv('LESSONWEAVE_EFFORT','medium')
    assert config.load(tmp_path)['generation']=={'model':'server-model','effort':'medium'}
    assert config.load(tmp_path)['translation']=={'model':'deepseek-flash','effort':'off'}
    translator=Backend(tmp_path,role='lean_translation')
    assert (translator.provider,translator.model,translator.effort)==('deepseek-official','deepseek-flash','off')
    config.update(tmp_path,config.DEFAULTS)
    assert config.load(tmp_path)==config.DEFAULTS


@pytest.mark.parametrize('value',[{},[],{'generation':{},'translation':{}},
    {'generation':{'model':[],'effort':'high'},'translation':{'model':'gpt-6-luna','effort':'max'}},
    {'generation':{'model':'gpt-6.1-sol','effort':'wrong'},'translation':{'model':'gpt-6-luna','effort':'max'}}])
def test_invalid_choices_do_not_write_a_settings_file(tmp_path,value):
    with pytest.raises(ValueError):config.update(tmp_path,value)
    assert not (tmp_path/'runtime/generation-settings.json').exists()
