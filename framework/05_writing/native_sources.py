"""从原生材料树取出真实内容，每份材料只建立一次来源索引"""
import copy
from collections import defaultdict
import hashlib
import io
import json
from pathlib import Path
import shutil
from urllib.parse import urlsplit, unquote
from zipfile import ZipFile


class NativeSources:
    def __init__(self, root, material):
        import book_sources as sources
        from source_disposition import evaluate
        self.root = Path(root).resolve()
        self.local_files = {}
        self.material = material
        self.sources = sources
        self.plan = sources._read(self.root / '04_transitions/transitions.json')
        self.questions = sources._read(self.root / self.plan['question_tree'])
        self.chapters = sources._read(self.root / self.plan['chapters_path'])
        self.nodes = {n['id']: n for n in sources._walk(material['tree'])}
        self.qnodes = {n['id']: n for n in sources._walk(self.questions['tree'])}
        self.sections = {n['id']: n for n in sources._walk(self.chapters['tree']) if n['kind'] == 'section'}
        self.by_question = defaultdict(list)
        self.owners = {}
        self.roles = {}
        for row in evaluate(self.questions, material)['nodes']:
            if row['role'] not in {'teach', 'preface', 'reference'}:
                continue
            owners = [qid for qid in row.get('question_ids', []) if qid in self.qnodes and not self.qnodes[qid]['children']]
            self.owners[row['material_node']] = owners
            self.roles[row['material_node']] = row['role']
            for qid in owners:
                self.by_question[qid].append(row['material_node'])
        self.asset_base = Path(material.get('asset_base') or root)
        self.repository = Path(material['repository']) if material.get('repository') else None
        self.file_bytes = {}
        self.document_kinds = {}
        self.visuals = {}
        self.assets = {}
        self.dom = None
        self.pdf = None
        original = material.get('original', {}).get('original', '')
        if material['kind'] == 'pdf':
            self.pdf = self.copy_file(Path(original), '00_source/materials/source-0001/original.pdf')
            import pymupdf
            with pymupdf.open(self.pdf) as document:
                self.pdf_heights = [page.rect.height for page in document]
        elif material['kind'] == 'web':
            self.web_archive = self._find_web_original(material)
            self.dom = None
            self._extract_archive(self.web_archive / 'original.wacz')
            self.copy_file(self.web_archive / 'original.html', '00_source/materials/source-0001/original.html')
            self.copy_file(self.web_archive / 'original.wacz', '00_source/materials/source-0001/original.wacz')
        if self.repository:
            sources._save(self.root / '00_source/source.json', {'repository': '00_source/materials/repository',
                           'original_repository': str(self.repository), 'material_run': material['run']})

    def copy_file(self, path, relative):
        if relative in self.local_files:
            return self.local_files[relative]
        target = self.root / relative
        if not target.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        self.local_files[relative]=target
        return target

    def _find_web_original(self, material):
        source = material['tree'].get('source', {}).get('url', '')
        from lessonweave.storage import Store
        # 冻结树保留原项目的回放入口，取材沿该入口找本机原件，不重新联网
        if source.startswith('/p/'):
            project, relative = source[3:].split('/', 1)
            for candidate in [self.root, *self.asset_base.parents]:
                if (candidate / relative).is_file():
                    return (candidate / relative).parent
            base = Path(__file__).resolve().parents[3]
            store_path = base / '30-browsertrix-formal-acquisition/site-data'
            if store_path.is_dir():
                try:
                    return (Path(Store(store_path).project(project)['path']) / relative).parent
                except KeyError:
                    pass
        raise FileNotFoundError('冻结网页没有找到对应的本机原件：' + source)

    def _extract_archive(self, archive):
        from warcio.archiveiterator import ArchiveIterator
        with ZipFile(archive) as z:
            for name in z.namelist():
                if not name.endswith('.warc.gz'):
                    continue
                with z.open(name) as stream:
                    for record in ArchiveIterator(stream):
                        if record.rec_type != 'response' or record.http_headers is None:
                            continue
                        mime = record.http_headers.get_header('Content-Type') or ''
                        if not mime.startswith('image/'):
                            continue
                        url = record.rec_headers.get_header('WARC-Target-URI')
                        suffix = Path(urlsplit(url).path).suffix or '.bin'
                        relative = '00_source/materials/source-0001/assets/' + hashlib.sha256(url.encode()).hexdigest()[:20] + suffix
                        target = self.root / relative
                        target.parent.mkdir(parents=True, exist_ok=True)
                        if not target.exists():
                            target.write_bytes(record.content_stream().read())
                        self.assets[url] = relative

    def _locator(self, node):
        source = copy.deepcopy(node.get('source') or {})
        kind = self.material['kind']
        if kind == 'code' and source.get('path'):
            relative = '00_source/materials/repository/' + source['path']
            source.update(kind='code', path=relative)
            return source
        if kind == 'pdf':
            provenance = source.get('provenance', [])
            location = provenance[0] if provenance else source
            source.update(kind='pdf', path='00_source/materials/source-0001/original.pdf',
                          page=location.get('page_no', source.get('page', 1)))
            bbox = location.get('bbox')
            if isinstance(bbox, dict):
                height = self.pdf_heights[int(source['page']) - 1]
                source['bbox'] = ([bbox['l'], height-bbox['t'], bbox['r'], height-bbox['b']]
                                  if bbox.get('coord_origin') == 'BOTTOMLEFT' else [bbox['l'],bbox['t'],bbox['r'],bbox['b']])
            return source
        source.update(kind='html', path='00_source/materials/source-0001/original.html')
        return source

    def _asset(self, node):
        if node.get('asset'):
            relative = '00_source/materials/source-0001/parsed-assets/' + node['asset']
            self.copy_file(self.asset_base / node['asset'], relative)
            return relative
        source = node.get('source', {})
        if source.get('src') in self.assets:
            return self.assets[source['src']]
        if node['type'] == 'svg' and source.get('selector'):
            if self.dom is None:
                from bs4 import BeautifulSoup
                self.dom = BeautifulSoup((self.web_archive / 'original.html').read_text('utf-8'), 'html.parser')
            element = self.dom.select_one(source['selector'])
            if element is not None:
                element['xmlns'] = 'http://www.w3.org/2000/svg'
                if 'viewbox' in element.attrs:
                    element['viewBox'] = element.attrs.pop('viewbox')
                if 'preserveaspectratio' in element.attrs:
                    element['preserveAspectRatio'] = element.attrs.pop('preserveaspectratio')
                target = self.root / ('00_source/materials/source-0001/assets/' + node['id'] + '.svg')
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(str(element), encoding='utf-8')
                return target.relative_to(self.root).as_posix()
        return None

    def pack(self, section_id, work):
        section = self.sections[section_id]
        qnodes = [self.qnodes[qid] for qid in section['question_ids'] if not self.qnodes[qid]['children']]
        requested = {q['id'] for q in qnodes}
        required = set(nid for qid in requested for nid in self.by_question[qid])
        records = []
        file_groups = defaultdict(list)
        visual_assets = []
        for nid in self.nodes:
            if nid not in required:
                continue
            node = self.nodes[nid]
            locator = self._locator(node)
            text = node.get('text', '')
            owners = sorted(requested & set(self.owners[nid]))
            record = {'id': nid, 'type': node['type'], 'source': locator, 'source_refs': [locator],
                      'question_ids': owners, 'child_ids': [c['id'] for c in node.get('children', [])],
                      'original_texts': {}, 'sentences': [], 'native_type': node['type']}
            if self.roles.get(nid) == 'reference':
                record.update(evidence_kind='material_index', reading_role='reference', reference_text=text)
                records.append(record)
                continue
            if self.repository and node.get('source', {}).get('path'):
                name = node['source']['path']; origin = self.repository / name
                if origin.is_file():
                    target = self.copy_file(origin, locator['path'])
                    # 写作取材沿用材料树的用途标记，不根据文件内容里的字符串降低读取范围
                    if self.sources._is_image(name):
                        record.update(type='image',asset='/'+locator['path'],original_media_type=node['type'])
                        visual=self.sources._add_visual(self.root,Path(work),record,self.visuals)
                        if visual:visual_assets.append(visual)
                        records.append(record)
                        continue
                    if node.get('state') == 'retained_resource' or node.get('reading_role') == 'resource':
                        record.update(type='file',asset='/'+locator['path'],coverage_scope='file_role',
                                      file_metadata={'path':locator['path'],'bytes':target.stat().st_size,
                                                     'role':'resource',
                                                     'declared_state':node.get('state')})
                        records.append(record)
                        continue
                    if name not in self.file_bytes:
                        self.file_bytes[name] = target.read_bytes()
                    data = self.file_bytes[name]
                    start = node['source'].get('start_byte', 0)
                    end = node['source'].get('end_byte', len(data))
                    if 'start_byte' not in node['source'] and node['source'].get('start_line'):
                        lines = data.splitlines(keepends=True)
                        start = sum(map(len, lines[:node['source']['start_line']-1]))
                        end = sum(map(len, lines[:node['source'].get('end_line',len(lines))]))
                    if name not in self.document_kinds:
                        is_document = origin.suffix.lower() in {'.md','.rst','.txt'} or node.get('state') == 'document'
                        if is_document and origin.suffix.lower() in {'.txt','.text',''}:
                            from document_sources import is_requirements,is_named_code
                            readable,_=self.sources._decode(data)
                            if is_named_code(origin)or(readable is not None and is_requirements(readable)):is_document=False
                        self.document_kinds[name]=is_document
                    is_document=self.document_kinds[name]
                    file_groups[(name,tuple(owners),is_document)].append((start,end,nid))
                    continue
                else:
                    record['unavailable_original'] = name
            if text:
                record['original_texts'][nid] = text
                if not record['sentences']:
                    record['sentences'] = self.sources._sentences(nid, text)
            asset = self._asset(node)
            if asset:
                record.update(asset='/' + asset, type='image', original_media_type=node['type'])
                visual = self.sources._add_visual(self.root, Path(work), record, self.visuals)
                if visual:
                    visual_assets.append(visual)
            records.append(record)
        # 文件、类、函数常常指向重叠的同一段源码，按实际字节区间合并，全部材料节点继续关联到原区间
        representation_links = []
        for (name, owners, is_document), spans in file_groups.items():
            data = self.file_bytes[name]
            merged = []
            for start,end,nid in sorted(spans):
                if merged and start <= merged[-1][1]:
                    merged[-1][1] = max(merged[-1][1],end)
                    merged[-1][2].append(nid)
                else:
                    merged.append([start,end,[nid]])
            for start,end,ids in merged:
                sid = next((nid for left,right,nid in spans if left==start and right==end),ids[0])
                text, _ = self.sources._decode(data[start:end])
                line = data[:start].count(b'\n') + 1
                locator = {'kind':'code','path':'00_source/materials/repository/'+name,
                           'start_byte':start,'end_byte':end,'start_line':line,
                           'end_line':line+max(0,len(data[start:end].splitlines())-1)}
                from document_sources import sentences as document_sentences
                record = {'id':sid,'source_ids':ids,'type':'paragraph'if is_document else'code',
                          'source':locator,'source_refs':[locator],'question_ids':list(owners),
                          'original_texts':{sid:text}if text is not None else{},
                          'sentences':document_sentences(sid,text,line)if text and is_document else
                              [{'id':f'{sid}.L{line}-L{locator["end_line"]}','original':text,
                                'start_line':line,'end_line':locator['end_line']}]if text else[]}
                if text is None:
                    record.update(type='file',asset='/'+locator['path'],coverage_scope='file_role')
                    visual=self.sources._add_visual(self.root,Path(work),record,self.visuals)
                    if visual:visual_assets.append(visual)
                elif not is_document:
                    record['verbatim_code']=True
                    for sentence in record['sentences']:sentence['verbatim_code']=True
                records.append(record)
                representation_links.extend({'material_node':nid,'canonical_source':sid,'path':name,
                                             'start_byte':start,'end_byte':end,'method':'overlapping_source_bytes'}for nid in ids)
        result = {'profile':'writing-raw-sources-v1','section_id':section_id,
                  'material_run':self.plan['material_run'],'material_path':self.plan['material_tree'],
                  'question_path':self.plan['question_tree'],'chapters_path':self.plan['chapters_path'],
                  'questions':copy.deepcopy(qnodes),'sources':records,'required_source_ids':[r['id'] for r in records],
                  'images':list(dict.fromkeys(v['model_path'] for v in visual_assets)), 'visual_assets':visual_assets,
                  'representation_links':representation_links,
                  'metadata':{'mapped_nodes':len(required),'included_nodes':len(records),'scope':'native_snapshot',
                              'original_assets_are_unchanged':True,'global_mapping_loaded_once':True}}
        self.sources._save(Path(work)/'source-pack.json', result)
        return result
