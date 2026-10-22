"""旧笔记别名仍可读取，缺少可选兼容文件时不重复发出 404 请求"""
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def test_project_metadata_reports_existing_optional_files_without_creating_them(tmp_path):
    from lessonweave.server import public_project
    project = {'id':'fixture','path':str(tmp_path),'legacy':1}
    assert public_project(project)['reader_files'] == {'whitespace':False,'note_aliases':False}
    writing = tmp_path/'05_writing';writing.mkdir()
    (writing/'reader-whitespace.json').write_text('{"replacements":{}}', 'utf-8')
    (writing/'demo.json').write_text('{"section_id":"old"}', 'utf-8')
    before = {p.name:p.read_bytes() for p in writing.iterdir()}
    value = public_project(project)
    assert value['reader_files'] == {'whitespace':True,'note_aliases':True}
    assert 'path' not in value
    assert {p.name:p.read_bytes() for p in writing.iterdir()} == before


@pytest.mark.parametrize('available',[False,True])
def test_optional_demo_probe_preserves_saved_aliases_and_reads_existing_old_notes(available):
    source = (ROOT/'framework/reader/writing-demo.js').read_text('utf-8')
    function = source[source.index('  async function loadNoteAliases('):source.index('\n  function note(',source.index('  async function loadNoteAliases('))]
    helpers = '''const data={transitions_path:'/transitions',section_id:'s1',transition_run:'run',
      units:[{question_id:'q1',note_block_id:'note',synthesis:{id:'current'}}],
      preview_note_aliases:[{question_id:'q1',current_block_id:'current',previous_block_id:'older'}]};
    const noteAliases=new Map(),requests=[];
    const fetch=async path=>{requests.push(path);return {ok:true,json:async()=>({validation:{passed:true},section_id:'s1',transitions_path:'/transitions',transition_run:'run',
      units:[{question_id:'q1',note_block_id:'saved-note',synthesis:{id:'saved-current'}}]})}};
    ''' + function + '\nwindow.check=async()=>{await loadNoteAliases(true);return {requests,aliases:[...noteAliases.values()].flat()}};'
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        page = browser.new_page();page.set_content('<!doctype html>')
        page.evaluate('available=>window.LESSONWEAVE={legacy:true,reader_files:{note_aliases:available}}',available)
        page.add_script_tag(content=helpers)
        result = page.evaluate('check()')
        browser.close()
    assert len(result['requests']) == int(available)
    assert any(value.endswith(':current') for value in result['aliases'])
    assert any(value.endswith(':older') for value in result['aliases'])
    assert any(value.endswith(':saved-note') for value in result['aliases']) == available
