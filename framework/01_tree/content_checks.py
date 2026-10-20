"""从原材料逐项核对内容，再检查树中所有本地文件引用"""
import json
import re
import unicodedata
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import unquote, urlsplit

import fitz
from bs4 import BeautifulSoup, Comment, NavigableString
from jsonschema import Draft202012Validator


PROFILE = 'content-tree-v1'
SKIP_TAGS = {'script', 'style', 'noscript', 'template', 'button', 'form'}


def original_image_url(value):
    # 回放地址和原站地址表示同一资源，尺寸、格式和查询参数仍保留
    return re.sub(r'^https?://[^/]+/archive/replay/.*?/\d{1,14}[a-z]*_/(?=https?://)','',value or '')


def image_asset(record,anchor,*addresses):
    items=record.get('images',[])
    direct=next((item['path'] for item in items if anchor and item.get('anchor')==anchor),None)
    if direct:return direct
    aliases={original_image_url(item['url']):item['path'] for item in items}
    return next((aliases[original_image_url(address)] for address in addresses if original_image_url(address) in aliases),None)


def walk(node):
    yield node
    for child in node['children']:
        yield from walk(child)


def normalized(text):
    # 只统一 Unicode、空白和断行软连字符，数学符号和标点仍参与内容核对
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', text).replace('\u00ad', ''))


def text_values(content):
    for key in ('text', 'raw_text', 'alt', 'rows', 'source_text'):
        value = content.get(key)
        if isinstance(value, str):
            yield value
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    yield item
                elif isinstance(item, list):
                    yield from (str(cell) for cell in item)
                elif isinstance(item, dict) and isinstance(item.get('text'), str):
                    yield item['text']


def nested_origins(value, location=''):
    if isinstance(value, dict):
        if value.get('kind') in ('file', 'pdf', 'html', 'code') and 'path' in value:
            yield location, value
        for key, child in value.items():
            yield from nested_origins(child, location + '/' + key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from nested_origins(child, location + '/' + str(index))


def material_body(soup):
    return soup.select_one('.body.markup') or soup.find('article') or soup.find('main') or soup.body


def in_material(element):
    return not any(parent.name in SKIP_TAGS for parent in [element, *element.parents] if getattr(parent, 'name', None))


def file_origin(root, path):
    from tree_code import file_source
    return file_source(root, path)


def web_origin(root, source, element, positions):
    # 旧快照可能只标记 body 的后代，裸正文仍按实际 body 范围保留
    located=next((p for p in [element,*element.parents]
                  if getattr(p,'get',None) and p.get('data-iqa-source') in positions),None)
    anchor=located.get('data-iqa-source') if located is not None else None
    snapshot=source['snapshot']
    return {**file_origin(root,root/source['entry']),'kind':'html','url':source['material'],
            'dom_path':f'[data-iqa-source="{anchor}"]' if anchor else 'body',
            'bbox':positions[anchor]['bbox'] if anchor else [0,0,snapshot['width'],snapshot['height']]}


def source_inventory(root, document, source):
    """分母直接从冻结的 PDF、HTML 或仓库清单取得，不使用树的统计反推"""
    root = Path(root)
    units = []
    if document['format'] == 'pdf':
        with fitz.open(root / source['entry']) as pdf:
            for page in pdf:
                origin = {**file_origin(root, root / source['entry']), 'kind': 'pdf',
                          'page': page.number + 1, 'bbox': list(page.rect)}
                units.append({'id': f'pdf-page-{page.number+1}', 'kind': 'page_visual', 'source': origin})
                index = 0
                for block in page.get_text('dict', flags=fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES)['blocks']:
                    for line in block.get('lines', []):
                        for span in line['spans']:
                            if not span['text'].strip():
                                continue
                            index += 1
                            units.append({'id': f'pdf-text-{page.number+1}-{index}', 'kind': 'text',
                                          'text': span['text'], 'source': {**origin, 'bbox': list(span['bbox'])}})
        scope = '逐页保留全部可视内容，并逐项提取 PDF 文本层的文字，扫描页的 OCR 对象另按 Docling 原始对象核对'
    elif document['format'] == 'html':
        soup = BeautifulSoup((root / source['entry']).read_text(encoding='utf-8'), 'html.parser')
        body = material_body(soup)
        if body is None:
            raise ValueError('本地快照中没有可提取的页面内容')
        positions = json.loads((root / source['positions']).read_text(encoding='utf-8'))
        roots = [body]
        for element in soup.select('h1.post-title,.subtitle,.byline-names time,.byline-names .author-name'):
            if element is not body and body not in element.parents:
                roots.append(element)
        seen = set()
        resources = {item['anchor']: item for item in source.get('resources', [])}
        for container in roots:
            for element in [container, *container.descendants]:
                if id(element) in seen:
                    continue
                seen.add(id(element))
                if isinstance(element, Comment) or not in_material(element):
                    continue
                parent = element.parent if isinstance(element, NavigableString) else element
                if not getattr(parent, 'get', None):
                    continue
                anchor = parent.get('data-iqa-source')
                if not anchor and parent.name not in {'body','html'}:
                    continue
                origin = web_origin(root,source,parent,positions)
                if isinstance(element, NavigableString) and str(element).strip():
                    units.append({'id': f'html-text-{len(units)+1}', 'kind': 'text', 'text': str(element), 'source': origin})
                elif getattr(element, 'name', None) == 'img':
                    from urllib.parse import urljoin
                    address = positions.get(anchor, {}).get('src') or urljoin(source['material'], element.get('src', ''))
                    path = image_asset(source,anchor,address,urljoin(source['material'],element.get('src','')),element.get('data-src',''))
                    units.append({'id': 'html-image-' + anchor, 'kind': 'image', 'asset': '/' + path if path else '', 'source': origin})
                elif getattr(element, 'name', None) in ('svg', 'canvas', 'video', 'audio', 'iframe', 'object', 'embed'):
                    item = resources.get(anchor, {})
                    units.append({'id': 'html-resource-' + anchor, 'kind': 'resource',
                                  'asset': '/' + item['path'] if item.get('path') else '', 'source': origin})
        scope = '覆盖本地快照中的正文容器、标题和作者信息，排除脚本、样式、模板及操作控件，其他页面内容仍保存在完整快照中'
    else:
        with zipfile.ZipFile(root / source['entry']) as archive:
            members = {item.filename for item in archive.infolist() if not item.is_dir()}
        if members != {item['archive_member'] for item in source['files']}:
            raise ValueError('仓库文件清单与 ZIP 中的实际成员不一致')
        for item in source['files']:
            units.append({'id': item['archive_member'], 'kind': 'file', 'source': {'kind': 'file', 'path': item['path']}})
        scope = '逐项保留输入仓库清单中的所有文件，源码细节继续按需展开'
    return {'profile': PROFILE, 'scope': scope, 'units': units}


def append_docling_units(root, document, inventory, output):
    path = output / 'docling.json'
    if document['format'] != 'pdf' or not path.is_file():
        return
    native = json.loads(path.read_text(encoding='utf-8'))
    pages = {page['number']: page for page in document['pages']}
    origin = file_origin(root, root / next(u['source']['path'] for u in inventory['units']))
    for group in ('texts', 'pictures', 'tables'):
        for item in native[group]:
            sources = []
            for provenance in item.get('prov', []):
                page = pages[provenance['page_no']]
                box = provenance['bbox']
                bbox = [box['l'], page['height']-box['t'], box['r'], page['height']-box['b']] if box.get('coord_origin') == 'BOTTOMLEFT' else [box['l'], box['t'], box['r'], box['b']]
                sources.append({**origin, 'kind': 'pdf', 'page': page['number'], 'bbox': [max(0, v) for v in bbox], 'engine_ref': item['self_ref']})
            source = sources[0] if sources else {**origin, 'engine_ref': item['self_ref']}
            inventory['units'].append({'id': 'docling-' + item['self_ref'], 'kind': 'text' if item.get('text', '').strip() else 'parser_object',
                                       'native_text':' | '.join(cell.get('text','') for cell in item.get('data',{}).get('table_cells',[])),
                                       **({'text': item['text']} if item.get('text', '').strip() else {}), 'source': source})


def location_matches(unit, origin, soup=None):
    source = unit['source']
    if source['kind'] != origin['kind'] or source['path'] != origin['path']:
        return False
    if source['kind'] == 'pdf':
        if source['page'] != origin.get('page'):
            return False
        a, b = source['bbox'], origin['bbox']
        overlap = max(0, min(a[2], b[2]+3)-max(a[0], b[0]-3)) * max(0, min(a[3], b[3]+3)-max(a[1], b[1]-3))
        return overlap >= max(0, a[2]-a[0])*max(0, a[3]-a[1]) * .5
    if source['kind'] == 'html':
        element = soup.get(source['dom_path'])
        owner = soup.get(origin['dom_path'])
        return element is not None and owner is not None and (element is owner or owner in element.parents)
    return True


def attach_missing_content(root, document, inventory, builder):
    """原文缺项直接补存到相应节点，找不到归属时放入明确的补充章节"""
    nodes = list(walk(document['tree']))
    soup = None
    if document['format'] == 'html':
        parsed = BeautifulSoup((root / inventory['units'][0]['source']['path']).read_text(encoding='utf-8'), 'html.parser') if inventory['units'] else None
        soup = {'body':parsed.body,'html':parsed.html,**{f'[data-iqa-source="{e["data-iqa-source"]}"]': e for e in parsed.find_all(attrs={'data-iqa-source': True})}} if parsed else {}
    regions = defaultdict(list)
    for node in nodes:
        for source in node['source']:
            regions[(source['kind'], source['path'], source.get('page'))].append((node, source))
    supplement = None
    recovered = 0
    for unit in inventory['units']:
        if unit['kind']=='parser_object':
            origin=unit['source']
            if any(s.get('engine_ref')==origin.get('engine_ref') for n in nodes for s in n['source']):
                continue
            if supplement is None:
                supplement=builder.node('section',{'text':'补充保留的原文'},document['tree']['source'])
                document['tree']['children'].append(supplement)
            content={'reason':'原生解析器已识别这个对象，但正文层级未接纳它，保留原对象的识别内容与原页区域','text':unit.get('native_text','')}
            if origin.get('kind')=='pdf' and origin.get('bbox'):
                box=fitz.Rect(origin['bbox'])
                if not box.is_empty:
                    target=root/'01_tree/history'/document['run']/'native-recovered'/('object-'+str(recovered+1)+'.png')
                    target.parent.mkdir(parents=True,exist_ok=True)
                    with fitz.open(root/origin['path']) as pdf:
                        pdf[origin['page']-1].get_pixmap(matrix=fitz.Matrix(2,2),clip=box,alpha=False).save(target)
                    content['asset']='/'+target.relative_to(root).as_posix()
            node=builder.node('unknown',content,[origin]);supplement['children'].append(node);nodes.append(node)
            regions[(origin['kind'],origin['path'],origin.get('page'))].append((node,origin))
            recovered+=1
            continue
        if unit['kind'] in ('image', 'resource'):
            if unit['asset'] and not any(n['content'].get('asset') == unit['asset'] for n in nodes):
                if supplement is None:
                    supplement = builder.node('section', {'text': '补充保留的原文'}, document['tree']['source'])
                    document['tree']['children'].append(supplement)
                asset = unit['asset']
                kind = 'image' if Path(asset).suffix.lower() in ('.png', '.svg', '.jpg', '.jpeg', '.webp', '.gif', '.avif') else 'unknown'
                content = {'asset': asset} if kind == 'image' else {'asset': asset, 'reason': '媒体原文件已经保留，内部内容尚未拆分'}
                node = builder.node(kind, content, [unit['source']])
                supplement['children'].append(node)
                nodes.append(node)
            continue
        if unit['kind'] != 'text':
            continue
        origin = unit['source']
        candidates = [node for node, source in regions[(origin['kind'], origin['path'], origin.get('page'))]
                      if location_matches(unit, source, soup)]
        text = normalized(unit['text'])
        if any(text in normalized(' '.join(text_values(node['content']))) for node in candidates):
            continue
        if candidates:
            node = min(candidates, key=lambda n: min((fitz.Rect(s['bbox']).get_area() for s in n['source'] if 'bbox' in s), default=1e20))
        else:
            if supplement is None:
                supplement = builder.node('section', {'text': '补充保留的原文'}, document['tree']['source'])
                document['tree']['children'].append(supplement)
            node = builder.node('paragraph', {'text': unit['text']}, [origin])
            supplement['children'].append(node)
        node['content'].setdefault('source_text', []).append({'text': unit['text'], 'source': origin})
        recovered += 1
    document['summary']['recovered_text_units'] = recovered


def coverage_report(root, document, inventory):
    nodes = list(walk(document['tree']))
    soup = None
    if document['format'] == 'html' and inventory['units']:
        parsed = BeautifulSoup((root / inventory['units'][0]['source']['path']).read_text(encoding='utf-8'), 'html.parser')
        soup = {'body':parsed.body,'html':parsed.html,**{f'[data-iqa-source="{e["data-iqa-source"]}"]': e for e in parsed.find_all(attrs={'data-iqa-source': True})}}
    node_text = {node['id']: normalized(' '.join(text_values(node['content']))) for node in nodes}
    regions = defaultdict(list)
    for node in nodes:
        for origin in node['source']:
            regions[(origin['kind'], origin['path'], origin.get('page'))].append((node, origin))
        for _, origin in nested_origins(node['content']):
            regions[(origin['kind'], origin['path'], origin.get('page'))].append((node, origin))
    entries = []
    for unit in inventory['units']:
        kind = unit['kind']
        origin = unit['source']
        candidates = regions[(origin['kind'], origin['path'], origin.get('page'))]
        owners = []
        if kind == 'page_visual':
            page = next((p for p in document['pages'] if p['number'] == origin['page']), None)
            if page and page.get('preview') and local_path(root, page['preview']).is_file():
                owners = [document['tree']['id']]
        elif kind == 'parser_object':
            owners = [n['id'] for n, s in candidates if s.get('engine_ref') == origin.get('engine_ref')]
        elif kind == 'file':
            owners = [n['id'] for n, _ in candidates if n['type'] == 'file']
        elif kind in ('image', 'resource'):
            owners = [n['id'] for n in nodes if unit['asset'] and n['content'].get('asset') == unit['asset']]
            if not owners and not unit['asset'] and kind=='image':
                owners=[n['id'] for n,s in candidates if n['content'].get('representation')=='original_page_region' and n['content'].get('asset') and location_matches(unit,s,soup)]
        else:
            text = normalized(unit['text'])
            for node, source in candidates:
                if location_matches(unit, source, soup) and text in node_text[node['id']]:
                    owners.append(node['id'])
        entries.append({'unit': unit['id'], 'kind': kind, 'nodes': sorted(set(owners)), 'passed': bool(owners)})
    missing = [entry['unit'] for entry in entries if not entry['passed']]
    counts = Counter(unit['kind'] for unit in inventory['units'])
    return {'profile': PROFILE, 'scope': inventory['scope'], 'expected': len(entries),
            'covered': len(entries) - len(missing), 'ratio': (len(entries) - len(missing)) / len(entries) if entries else 1,
            'types': dict(counts), 'missing': missing, 'entries': entries}


def local_path(root, value, raw=False):
    if raw:
        path = (Path(root) / value).resolve()
        if not path.is_relative_to(Path(root).resolve()):
            raise ValueError('来源路径超出了项目目录：' + value)
        return path
    address = urlsplit(value)
    if address.scheme or address.netloc:
        raise ValueError('内容引用仍是网络地址，尚未保存到本地：' + value)
    path = (Path(root) / unquote(address.path).lstrip('/')).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise ValueError('本地对象路径超出了项目目录：' + value)
    return path


def check_objects(root, document, source_schema):
    errors = []
    checked = 0
    ids = {n['id'] for n in walk(document['tree'])}
    pages = {p['number']: p for p in document['pages']}
    html_cache = {}
    raw_cache = {}
    width = document.get('snapshot', {}).get('width', 0)
    height = document.get('snapshot', {}).get('height', 0)
    origins = [(n['id'] + location, origin) for n in walk(document['tree'])
               for location, origin in nested_origins({'source': n['source'], 'content': n['content']})]
    origins += [('relations/' + str(i) + location, origin) for i, edge in enumerate(document['relations'])
                for location, origin in nested_origins(edge['source'])]
    validator = Draft202012Validator({'$ref': '#/$defs/source', '$defs': {'source': source_schema}})
    for location, origin in origins:
        checked += 1
        clean = {k: v for k, v in origin.items() if k not in ('syntax_type', 'missing')}
        issues = list(validator.iter_errors(clean))
        if issues:
            errors.append(location + ' 的来源字段不符合 Schema：' + issues[0].message)
            continue
        try:
            path = local_path(root, origin['path'], raw=True)
            if not path.is_file():
                raise ValueError('来源文件不存在：' + origin['path'])
            if origin['kind'] == 'pdf':
                page = pages.get(origin['page'], {})
                x0, y0, x1, y1 = origin['bbox']
                if not 0 <= x0 <= x1 <= page.get('width', 0) + 1 or not 0 <= y0 <= y1 <= page.get('height', 0) + 1:
                    raise ValueError('PDF 来源位置超出页面')
            elif origin['kind'] == 'html':
                if path not in html_cache:
                    html_cache[path] = BeautifulSoup(path.read_text(encoding='utf-8'), 'html.parser')
                if html_cache[path].select_one(origin['dom_path']) is None:
                    raise ValueError('本地 DOM 中没有对应元素')
                x0, y0, x1, y1 = origin['bbox']
                if x1 < x0 or y1 < y0 or width and x1 > width + 1 or height and y1 > height + 1:
                    raise ValueError('网页来源位置超出快照')
            elif origin['kind'] == 'code':
                if path not in raw_cache:
                    raw_cache[path] = path.read_bytes()
                raw = raw_cache[path]
                start, end = origin['start_byte'], origin['end_byte']
                if not 0 <= start <= end <= len(raw):
                    raise ValueError('源码范围超出文件')
                expected = (raw[:start].count(b'\n') + 1, raw[:max(start, end - 1)].count(b'\n') + 1)
                if expected != (origin['start_line'], origin['end_line']):
                    raise ValueError('源码行号与字节位置不一致')
        except (ValueError, OSError, SyntaxError) as error:
            errors.append(location + '：' + str(error))
    assets = [('original', document['original'])]
    assets += [('pages/' + str(p['number']), p['preview']) for p in document['pages']]
    assets += [('snapshot/' + k, v) for k, v in document.get('snapshot', {}).items() if k in ('image', 'html', 'offline_html')]
    assets += [(n['id'] + '/asset', n['content']['asset']) for n in walk(document['tree']) if n['content'].get('asset')]
    for location, asset in assets:
        checked += 1
        try:
            path = local_path(root, asset)
            if not path.is_file() or path.stat().st_size == 0:
                raise ValueError('引用的本地对象不存在或为空：' + asset)
            if path.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.avif'):
                from PIL import Image
                with Image.open(path) as image:
                    image.verify()
            elif path.suffix.lower() == '.svg':
                import xml.etree.ElementTree as ET
                if not ET.parse(path).getroot().tag.endswith('svg'):
                    raise ValueError('保存的 SVG 没有有效的图像根节点')
        except (ValueError, OSError) as error:
            errors.append(location + '：' + str(error))
    for node in walk(document['tree']):
        for key in ('file_ref', 'evidence_file'):
            if node['content'].get(key):
                checked += 1
                if node['content'][key] not in ids:
                    errors.append(node['id'] + ' 的 ' + key + ' 没有对应节点')
    return {'expected': checked, 'checked': checked, 'available': checked-len(errors),
            'ratio': (checked-len(errors))/checked if checked else 1, 'errors': errors}


def normalize_content(tree):
    for node in walk(tree):
        content = node['content']
        content.setdefault('source_text', [])
        if node['type'] == 'module':
            content.setdefault('ports', [])
            content.setdefault('unresolved_references', [])
        if node['type'] == 'entrypoint':
            content.setdefault('actions', [])
        if node['type'] == 'list':
            content.setdefault('ordered', False)
            content.setdefault('start', 1)
            content['items'] = len(node['children'])
            for index, child in enumerate(node['children'], content['start']):
                if child['type'] == 'list_item':
                    child['content'].setdefault('ordinal', index)
                    if not str(child['content'].get('marker', '')).strip():
                        child['content']['marker'] = str(index) if content['ordered'] else '•'


def evaluate_content(root, document):
    inventory_path = local_path(root, document['coverage']['inventory'], raw=True)
    inventory = json.loads(inventory_path.read_text(encoding='utf-8'))
    source = json.loads((inventory_path.parent / 'source.json').read_text(encoding='utf-8'))
    expected = source_inventory(root, document, source)
    append_docling_units(root, document, expected, inventory_path.parent)
    if inventory != expected:
        raise ValueError('内容清单与原材料不一致，必须重新从原材料建立清单')
    schema = json.loads((root / '01_tree/tree.schema.json').read_text(encoding='utf-8'))
    return coverage_report(root, document, inventory), check_objects(root, document, schema['$defs']['source'])
