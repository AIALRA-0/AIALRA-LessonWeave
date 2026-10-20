"""从当前原件读取原句位置，材料包与讲解正文保持原样"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import html
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlparse
import unicodedata


PROFILE = "reading-source-locations-v1"
PRINTING = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "−": "-", "\u00ad": ""})


def load(path):
    return json.loads(Path(path).read_text("utf-8"))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", "utf-8")


def local(root, value):
    """只读取当前案例内真实存在的文件，网页外链不会被当作本地路径"""
    value = str(value or "")
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https", "data", "javascript"} or value.startswith("//"):
        return None
    candidate = Path(unquote(parsed.path if parsed.scheme == "file" else value).lstrip("/"))
    if not candidate.is_absolute():
        candidate = Path(root) / candidate
    candidate = candidate.resolve()
    try:
        candidate.relative_to(Path(root).resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def url(root, path):
    return "/" + Path(path).resolve().relative_to(Path(root).resolve()).as_posix()


def normalized_map(text):
    """只忽略打印空白和等价字形，数字、单词及语句顺序继续逐字匹配"""
    letters, offsets = [], []
    for index, char in enumerate(text):
        for letter in unicodedata.normalize("NFKC", char).translate(PRINTING).casefold():
            if not letter.isspace():
                letters.append(letter)
                offsets.append(index)
    return "".join(letters), offsets


def unique_span(original, actual, prepared=None):
    needle = normalized_map(original)[0]
    haystack, offsets = prepared if prepared is not None else normalized_map(actual)
    if not needle:
        return None, "unavailable"
    matches=[]
    start=haystack.find(needle)
    while start>=0:
        first,last=offsets[start],offsets[start+len(needle)-1]+1
        before=actual[first-1] if first else ""
        after=actual[last] if last<len(actual) else ""
        invalid_left=needle[0].isalnum() and bool(before) and before.isalnum()
        invalid_right=needle[-1].isalnum() and bool(after) and after.isalnum()
        if re.fullmatch(r"[-+]?\d+(?:\.\d+)?",needle):
            invalid_left=invalid_left or bool(before) and before in ".+-"
            invalid_right=invalid_right or bool(after) and after in ".0123456789"
        if not invalid_left and not invalid_right:
            matches.append((first,last))
        start=haystack.find(needle,start+1)
    if not matches:
        return None, "unavailable"
    if len(matches)>1:
        return None, "ambiguous"
    return matches[0], "exact"


def line_boxes(items):
    groups = defaultdict(list)
    for page, line, box in items:
        groups[(page, line)].append(box)
    return [{"page_id": page, "bbox": [round(min(box[0] for box in boxes), 3), round(min(box[1] for box in boxes), 3),
                                        round(max(box[2] for box in boxes), 3), round(max(box[3] for box in boxes), 3)]}
            for (page, _), boxes in groups.items()]


def collect_packs(paths):
    groups = {}
    for path in sorted(map(Path, paths)):
        pack = load(path)
        key = (pack.get("material_run"), pack.get("material_path"))
        if not all(key):
            raise ValueError(f"材料包没有冻结版本与材料路径: {path}")
        group = groups.setdefault(key, {"material_run": key[0], "material_path": key[1], "sources": {}, "pack_paths": []})
        group["pack_paths"].append(str(path))
        for source in pack.get("sources", []):
            locator=deepcopy(source.get('source',{}))
            if locator.get('selector')and not locator.get('dom_path'):locator['dom_path']=locator['selector']
            record = group["sources"].setdefault(source["id"], {"id": source["id"], "type": source.get("type"),
                "source": locator, "source_refs": deepcopy(source.get("source_refs", [])),
                "file_fragments": deepcopy(source.get("file_fragments", [])), "asset": source.get("asset"), "sentences": {}})
            if source.get("asset"):
                if record.get("asset") and record["asset"] != source["asset"]:
                    raise ValueError(f"同一材料版本的原图不同: {source['id']}")
                record["asset"] = source["asset"]
            for sentence in source.get("sentences", []):
                old = record["sentences"].get(sentence["id"])
                if old and old["original"] != sentence["original"]:
                    variants=old.setdefault('original_variants',[old['original']])
                    if sentence['original']not in variants:variants.append(sentence['original'])
                    old['location_note']='同一行范围内保留多个原始片段，定位显示原文件的完整行'
                    old['location_conflict']=not(old.get('verbatim_code')and sentence.get('verbatim_code')and
                        old.get('start_line')==sentence.get('start_line')and old.get('end_line')==sentence.get('end_line'))
                if not old:
                    record["sentences"][sentence["id"]] = deepcopy(sentence)
    return list(groups.values())


def _sentence_record(sentence):
    return {"id": sentence["id"], "original": sentence["original"], "status": "unavailable", "rects": [],
            "reason": "当前原件尚未提供可逐字核对的句子坐标"}


def _pdf_characters(page, page_id, boxes=None, dehyphenate=False):
    import fitz
    text, positions = [], []
    for block_index, block in enumerate(page.get_text("rawdict", sort=True)["blocks"]):
        for line_index, line in enumerate(block.get("lines", [])):
            chars = [char for span in line.get("spans", []) for char in span.get("chars", [])]
            for index, char in enumerate(chars):
                box = char["bbox"]
                if boxes and not any(fitz.Rect(target).contains(fitz.Point((box[0]+box[2])/2, (box[1]+box[3])/2)) for target in boxes):
                    continue
                # 原 PDF 行尾的断词连字符只影响排版，保留其他位置的全部符号
                if dehyphenate and index == len(chars)-1 and char["c"] == "-":
                    continue
                text.append(char["c"])
                positions.append((page_id, (block_index, line_index), box))
            text.append("\n")
            positions.append(None)
    return "".join(text), positions


def prepare_pdf(root, group, out, manifest):
    import fitz
    documents, caches = {}, {}
    try:
        for source in group["sources"].values():
            refs = [ref for ref in source["source_refs"] or [source["source"]] if ref.get("kind") == "pdf" and ref.get("page")]
            if not refs:
                continue
            record = manifest["sources"][source["id"]]
            chunks, positions = [], []
            by_page = defaultdict(list)
            for ref in refs:
                path = local(root, ref.get("path"))
                if path:
                    by_page[(path, int(ref["page"]))].append(ref.get("bbox"))
            for (path, number), boxes in by_page.items():
                doc = documents.setdefault(path, fitz.open(path)) if path not in documents else documents[path]
                if not 1 <= number <= len(doc):
                    continue
                page = doc[number-1]
                page_id = path.relative_to(root).as_posix()+":"+str(number)
                if page_id not in manifest["pages"]:
                    target = out / "pages" / f"page-{len(manifest['pages'])+1:04d}.png"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    page.get_pixmap(matrix=fitz.Matrix(1.5,1.5), alpha=False).save(target)
                    manifest["pages"][page_id] = {"kind": "pdf", "number": number, "path": path.relative_to(root).as_posix(),
                        "image": url(root,target), "width": page.rect.width, "height": page.rect.height, "coordinate_space": "pdf_points"}
                record["page_ids"].append(page_id)
                for box in boxes:
                    if box:
                        record["locations"].append({"page_id": page_id, "bbox": box, "precision": "source_region"})
                cache_key = (path, number, tuple(tuple(box) for box in boxes if box))
                if cache_key not in caches:
                    caches[cache_key] = _pdf_characters(page,page_id,[box for box in boxes if box] or None)
                raw, mapping = caches[cache_key]
                chunks.append(raw);positions.extend(mapping)
            observed = "".join(chunks)
            for sid, sentence in source["sentences"].items():
                result = record["sentences"][sid]
                if sentence.get("evidence_kind") == "material_index":
                    continue
                span, status = unique_span(sentence["original"], observed)
                mapping=positions
                if not span:
                    joined,joined_positions=[],[]
                    for (path, number), boxes in by_page.items():
                        page_id=path.relative_to(root).as_posix()+":"+str(number)
                        key=(path,number,tuple(tuple(box) for box in boxes if box),"dehyphenate")
                        if key not in caches:
                            caches[key]=_pdf_characters(documents[path][number-1],page_id,[box for box in boxes if box] or None,True)
                        raw,locations=caches[key];joined.append(raw);joined_positions.extend(locations)
                    span,status=unique_span(sentence["original"],"".join(joined));mapping=joined_positions
                # 框内缺少断行字形时，只在该来源声明的真实页面内重新核对完整原句
                if not span:
                    whole, whole_positions = [], []
                    for (path, number) in by_page:
                        page_id=path.relative_to(root).as_posix()+":"+str(number)
                        raw,mapping=_pdf_characters(documents[path][number-1],page_id)
                        whole.append(raw);whole_positions.extend(mapping)
                    span,status=unique_span(sentence["original"],"".join(whole));mapping=whole_positions
                    if not span:
                        whole,whole_positions=[],[]
                        for (path, number) in by_page:
                            page_id=path.relative_to(root).as_posix()+":"+str(number)
                            raw,locations=_pdf_characters(documents[path][number-1],page_id,None,True)
                            whole.append(raw);whole_positions.extend(locations)
                        span,status=unique_span(sentence["original"],"".join(whole));mapping=whole_positions
                if span:
                    result.update(status="exact",method="pdf_text_characters",rects=line_boxes(item for item in mapping[span[0]:span[1]] if item),reason="原句已与原 PDF 的字符逐字对应")
                else:
                    result.update(status=status,rects=[],reason="原句在当前 PDF 字符层中尚未唯一匹配，保留原页供对照")
    finally:
        for doc in documents.values():
            doc.close()


WEB_CSS = """html{color-scheme:light}body{max-width:850px;margin:24px auto;padding:0 18px;font:16px/1.9 'Segoe UI','Microsoft YaHei',sans-serif;color:#232321;background:white}img{max-width:100%;height:auto}figure{margin:24px 0}p{margin:18px 0}pre{white-space:pre-wrap}figcaption{font-size:13px}mark{background:#ffe1a1;color:inherit;box-shadow:0 0 0 1px #b77714}.location-selected{outline:2px solid #b77714;outline-offset:5px;scroll-margin-block:32px}.code-lines{font:14px/1.8 Consolas,monospace;white-space:pre}.code-line{display:block;min-height:1.8em}.code-line::before{content:attr(data-line);display:inline-block;min-width:5em;color:#777;user-select:none}.code-line.location-selected{background:#ffe1a1;outline:0} """


def _html_document(body):
    return '<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src \'self\' data:; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'"><style>'+WEB_CSS+'</style></head><body>'+body+'</body></html>'


def prepare_web_dom(root, group, out, tree):
    from bs4 import BeautifulSoup
    snapshot=tree.get("snapshot",{})
    declared=tree.get('original')
    original=local(root,declared if isinstance(declared,str)else None) or local(root,snapshot.get("html"))
    if not original:
        original=next((path for source in group['sources'].values()
            if source.get('source',{}).get('kind')=='html'and (path:=local(root,source['source'].get('path')))and path.suffix.lower()in {'.html','.htm'}),None)
    if not original or original.suffix.lower() not in {".html",".htm"}:
        return None
    soup=BeautifulSoup(original.read_text("utf-8"),"html.parser")
    selected=[]
    for source_key,source in group["sources"].items():
        selector=source["source"].get("dom_path")
        try:
            node=soup.select_one(selector) if selector else None
        except Exception:
            node=None
        if node is not None:
            markers=node.get('data-lw-source','').split()
            source_id=source.get('id',source_key)
            if source_id not in markers:markers.append(source_id)
            node['data-lw-source']=' '.join(markers)
            selected.append(node)
            if source.get("asset"):
                image=node if node.name=="img" else node.find("img")
                asset=local(root,source["asset"])
                if image and asset:
                    image["src"]=url(root,asset)
    selected_ids={id(node) for node in selected}
    roots=[node for node in soup.find_all(True) if id(node) in selected_ids and not any(id(parent) in selected_ids for parent in node.parents)]
    body="\n".join(str(node) for node in roots)
    clean=BeautifulSoup(body,"html.parser")
    for node in clean.select("script,style,link,base,iframe,object,embed,form,meta"):
        node.decompose()
    for node in clean.find_all(True):
        for key in list(node.attrs):
            if key.lower().startswith("on") or key in {"srcset","sizes","style","poster","background","href","action"}:
                del node[key]
        if node.name=="img":
            path=local(root,node.get("src"))
            if path:
                node["src"]=url(root,path)
            else:
                node.attrs.pop("src",None)
    target=out/"web-dom.html"
    target.write_text(_html_document(str(clean)),"utf-8")
    return target


WEB_MEASURE_JS = r"""sources => {
 const normalize = text => {const chars=[],offsets=[];let p=0;for(const c of text){for(let x of c.normalize('NFKC').toLowerCase()){x=x.replace(/[‘’]/g,"'").replace(/[“”]/g,'"').replace(/[–—−]/g,'-').replace(/\u00ad/g,'');if(!/\s/u.test(x)&&x){chars.push(x);offsets.push(p);}}p+=c.length;}return {text:chars.join(''),offsets};};
 const result={};
 for(const source of sources){
  let target;try{target=document.querySelector('[data-lw-source~="'+CSS.escape(source.id)+'"]')||document.querySelector(source.source.dom_path);}catch{}
  const item={bbox:null,sentences:{}};result[source.id]=item;
  if(!target)continue;
  const bounds=target.getBoundingClientRect();item.bbox=[bounds.left+scrollX,bounds.top+scrollY,bounds.right+scrollX,bounds.bottom+scrollY];
  const nodes=[];let raw='',node;const walker=document.createTreeWalker(target,NodeFilter.SHOW_TEXT);
  while(node=walker.nextNode()){if(node.parentElement.closest('script,style'))continue;nodes.push({node,start:raw.length});raw+=node.textContent;}
  const actual=normalize(raw);
  for(const sentence of Object.values(source.sentences)){
   if(sentence.evidence_kind==='material_index')continue;
   const needle=normalize(sentence.original).text,start=actual.text.indexOf(needle);
   if(!needle||start<0){item.sentences[sentence.id]={status:'unavailable',rects:[]};continue;}
   if(actual.text.indexOf(needle,start+1)>=0){item.sentences[sentence.id]={status:'ambiguous',rects:[]};continue;}
   const a=actual.offsets[start],b=actual.offsets[start+needle.length-1]+1;
   const first=nodes.find(n=>a>=n.start&&a<n.start+n.node.length),last=[...nodes].reverse().find(n=>b>n.start&&b<=n.start+n.node.length);
   if(!first||!last)continue;
   const range=document.createRange();range.setStart(first.node,a-first.start);range.setEnd(last.node,b-last.start);
   const rects=[...range.getClientRects()].filter(r=>r.width>0&&r.height>0).map(r=>[r.left+scrollX,r.top+scrollY,r.right+scrollX,r.bottom+scrollY]);
   const unique=[...new Map(rects.map(r=>[r.map(n=>n.toFixed(3)).join(','),r])).values()];
   item.sentences[sentence.id]={status:'exact',rects:unique,dom_span:[a,b]};
  }
 }
 return result;
}"""


def prepare_web(root, group, out, manifest, tree):
    target=prepare_web_dom(root,group,out,tree)
    if not target:
        return
    from functools import partial
    from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
    from threading import Thread
    from playwright.sync_api import sync_playwright
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self,*args):
            pass
    server=ThreadingHTTPServer(("127.0.0.1",0),partial(Handler,directory=str(root)))
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with sync_playwright() as play:
            browser=play.chromium.launch(headless=True)
            page=browser.new_page(viewport={"width":1280,"height":1000},device_scale_factor=1)
            external=[]
            def route(req):
                if req.request.url.startswith(f"http://127.0.0.1:{server.server_port}/") or req.request.url.startswith("data:"):
                    req.continue_()
                else:
                    external.append(req.request.url);req.abort()
            page.route("**/*",route)
            page.goto(f"http://127.0.0.1:{server.server_port}"+url(root,target),wait_until="networkidle")
            page.evaluate("async()=>{await document.fonts.ready;await Promise.all([...document.images].map(img=>img.complete?Promise.resolve():new Promise(r=>{img.onload=r;img.onerror=r})));}")
            observed=page.evaluate(WEB_MEASURE_JS,list(group["sources"].values()))
            width,height=page.evaluate("[document.documentElement.scrollWidth,document.documentElement.scrollHeight]")
            screenshot=out/"web-page.png";page.screenshot(path=str(screenshot),full_page=True)
            browser.close()
        if external:
            raise ValueError("离线原件仍尝试读取外部资源: "+str(external))
        manifest["web"]={"image":url(root,screenshot),"width":width,"height":height,"dom":url(root,target),"kind":"html","coordinate_space":"css_pixels"}
        manifest["pages"]["web"]=manifest["web"]
        for sid,item in observed.items():
            record=manifest["sources"][sid];record["page_ids"]=["web"]
            if item["bbox"]:
                record["locations"]=[{"page_id":"web","bbox":item["bbox"],"precision":"source_region"}]
            for sentence_id,located in item["sentences"].items():
                record["sentences"][sentence_id].update(located,method="dom_range",dom_path=record["source"].get("dom_path"),
                    reason="原句已在当前离线 DOM 中逐字对应" if located["status"]=="exact" else "原句在当前 DOM 中尚未唯一匹配")
                record["sentences"][sentence_id]["rects"]=[{"page_id":"web","bbox":box} for box in located["rects"]]
    finally:
        server.shutdown();server.server_close()


def _file_text(path,encoding):
    data=path.read_bytes()
    for name in dict.fromkeys([encoding,"utf-8-sig","utf-16" if data.startswith((b'\xff\xfe',b'\xfe\xff')) else "cp1252"]):
        if not name:
            continue
        try:
            return data.decode(name)
        except (UnicodeError,LookupError):
            pass
    return None


def prepare_code(root,group,out,manifest):
    files={};existing_files={item['path']:item['id']for item in manifest['files'].values()}
    next_file=len(manifest['files'])+1
    for source in group["sources"].values():
        if not any(sentence.get("evidence_kind")!="material_index" for sentence in source["sentences"].values()):
            continue
        fragments=source.get("file_fragments",[])
        refs=[(fragment.get("source",{}),fragment.get("encoding")) for fragment in fragments]
        if not refs and source["source"].get("kind")=="code":
            refs=[(source["source"],None)]
        record=manifest["sources"][source["id"]]
        for ref,encoding in refs:
            path=local(root,ref.get("path"))
            if not path:
                continue
            if path.suffix.lower() in {".svg",".png",".jpg",".jpeg",".gif",".webp",".pdf"}:
                continue
            text=_file_text(path,encoding)
            if text is None:
                continue
            relative=path.relative_to(root).as_posix()
            lines=text.splitlines(keepends=True)
            begin=max(1,int(ref.get("start_line",1)));end=min(len(lines),int(ref.get("end_line",len(lines))))
            scope="".join(lines[begin-1:end]);offset=sum(map(len,lines[:begin-1]))
            if "start_byte" in ref or "end_byte" in ref:
                data=path.read_bytes();start_byte=int(ref.get("start_byte",0));end_byte=int(ref.get("end_byte",len(data)))
                decoded=False
                for codec in dict.fromkeys([encoding,"utf-8-sig","utf-16" if data.startswith((b'\xff\xfe',b'\xfe\xff')) else "cp1252"]):
                    if not codec:
                        continue
                    try:
                        prefix=data[:start_byte].decode(codec);fragment=data[start_byte:end_byte].decode(codec)
                    except (UnicodeError,LookupError):
                        continue
                    if text.startswith(prefix) and text[len(prefix):len(prefix)+len(fragment)]==fragment:
                        scope=fragment;offset=len(prefix);decoded=True;break
                if not decoded:
                    continue
            prepared=normalized_map(scope)
            for sid,sentence in source["sentences"].items():
                if sentence.get("evidence_kind")=="material_index" or record["sentences"][sid]["status"]=="exact":
                    continue
                span,status=unique_span(sentence["original"],scope,prepared)
                result=record["sentences"][sid]
                if not span:
                    result.update(status=status,reason="原句尚未在来源声明的实际文件范围内唯一匹配")
                    continue
                a,b=offset+span[0],offset+span[1]
                first=text.count("\n",0,a)+1;last=text.count("\n",0,max(a,b-1))+1
                if relative not in files:
                    fileid=existing_files.get(relative)
                    if fileid is None:fileid=f'file-{next_file:04d}';next_file+=1
                    files[relative]={"id":fileid,"path":relative,"text":text,"line_count":len(lines)}
                fileid=files[relative]['id']
                result.update(status="exact",method="file_text_lines",reason="原句已与实际文件内容逐字核对",file_id=fileid,
                    path=relative,start_line=first,end_line=last,start_column=a-text.rfind("\n",0,a)-1,end_column=b-text.rfind("\n",0,b)-1)
                if fileid not in record["file_ids"]:
                    record["file_ids"].append(fileid)
    for item in files.values():
        target=out/"files"/(item["id"]+".html");target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(_html_document('<pre class="code-lines">'+"".join('<span class="code-line" id="L'+str(i)+'" data-line="'+str(i)+'">'+html.escape(line.rstrip("\r\n"))+'</span>' for i,line in enumerate(item.pop("text").splitlines(),1))+'</pre>'),"utf-8")
        manifest["files"][item["id"]]={**item,"dom":url(root,target)}


def prepare_assets(root, group, manifest):
    from PIL import Image
    from bs4 import BeautifulSoup
    for sid,source in group["sources"].items():
        record=manifest["sources"][sid]
        if record["page_ids"] or not source.get("asset"):
            continue
        path=local(root,source["asset"])
        if not path:
            continue
        try:
            if path.suffix.lower()==".svg":
                svg=BeautifulSoup(path.read_text("utf-8"),"xml").find("svg")
                view=[float(value) for value in re.split(r"[\s,]+",svg.get("viewBox","").strip()) if value]
                width,height=(view[2],view[3]) if len(view)==4 else (float(re.match(r"[\d.]+",svg.get("width","0"))[0]),float(re.match(r"[\d.]+",svg.get("height","0"))[0]))
            else:
                with Image.open(path) as image:
                    width,height=image.size
            if width<=0 or height<=0:
                continue
        except (ValueError,TypeError,KeyError,AttributeError,OSError):
            continue
        page_id="asset:"+path.relative_to(root).as_posix()
        manifest["pages"][page_id]={"kind":"image","image":url(root,path),"width":width,"height":height,"coordinate_space":"asset_pixels"}
        record["page_ids"].append(page_id)


def prepare_image_text(root, group, out, manifest):
    """原图中文字只有与实际识别字符完整唯一对应时才取得句框"""
    import importlib.util
    if importlib.util.find_spec('rapidocr_onnxruntime') is None:
        manifest['optional_image_ocr'] = {'available': False, 'reason': '当前保留原图区域定位，图内文字尚未取得独立 OCR 句框'}
        return
    import numpy as np
    from PIL import Image
    from rapidocr_onnxruntime import RapidOCR
    engine=None; cache={};evidence=[]
    for sid,source in group["sources"].items():
        record=manifest["sources"][sid]
        pending=[sentence for sentence_id,sentence in source["sentences"].items()
                 if sentence.get("evidence_kind")!="material_index" and record["sentences"][sentence_id]["status"]!="exact"]
        path=local(root,source.get("asset"))
        if not pending or not path:
            continue
        if path not in cache:
            if path.suffix.lower()==".svg":
                import cairosvg
                preview=out/"image-previews"/f"image-{len(cache)+1:04d}.png";preview.parent.mkdir(parents=True,exist_ok=True)
                cairosvg.svg2png(url=str(path),write_to=str(preview),scale=1.5)
                raster=preview
            else:
                raster=path
            try:
                with Image.open(raster) as original:
                    picture=original.convert("RGB")
            except OSError:
                continue
            if engine is None:
                engine=RapidOCR(intra_op_num_threads=2,inter_op_num_threads=2)
            rows,_=engine(np.asarray(picture),use_cls=False,return_word_box=True)
            chars=[];locations=[]
            for number,row in enumerate(rows or []):
                evidence.append({"asset":url(root,path),"line":number,"text":row[1],"confidence":float(row[2])})
                if len(row)<5 or len(row[3])!=len(row[4]):
                    continue
                for quad,char in zip(row[3],row[4]):
                    box=[min(point[0] for point in quad),min(point[1] for point in quad),max(point[0] for point in quad),max(point[1] for point in quad)]
                    chars.extend(char);locations.extend((number,box) for _ in char)
                chars.append("\n");locations.append(None)
            cache[path]=("".join(chars),locations,picture.width,picture.height)
        actual,mapping,width,height=cache[path]
        page_id=record["page_ids"][0] if record["page_ids"] else None
        if not page_id:
            continue
        page=manifest["pages"][page_id]
        if page["kind"] in {"html","pdf"}:
            image_box=next((item["bbox"] for item in record["locations"] if item["page_id"]==page_id),None)
            if not image_box:
                continue
        else:
            image_box=[0,0,page["width"],page["height"]]
        for sentence in pending:
            span,status=unique_span(sentence["original"],actual)
            result=record["sentences"][sentence["id"]]
            if not span:
                if status=="ambiguous":
                    result.update(status=status,reason="原图中存在多个同样的文字，尚未取得唯一句框")
                continue
            matched=[]
            for item in mapping[span[0]:span[1]]:
                if not item:
                    continue
                line,box=item
                x0,y0,x1,y1=image_box
                matched.append((page_id,line,[x0+box[0]/width*(x1-x0),y0+box[1]/height*(y1-y0),x0+box[2]/width*(x1-x0),y0+box[3]/height*(y1-y0)]))
            if matched:
                result.update(status="exact",method="image_ocr_characters",rects=line_boxes(matched),
                              reason="原句已与原图识别字符逐字对应，句框来自实际识别位置",asset=url(root,path))
    if evidence:
        save(out/"image-ocr-evidence.json",evidence)


def prepare_locations(root,pack_paths,out=None):
    root=Path(root).resolve();out=Path(out).resolve() if out else root/"05_writing/source-location"
    out.mkdir(parents=True,exist_ok=True)
    index={"profile":PROFILE,"coordinate_format":"xyxy","versions":[]}
    for number,group in enumerate(collect_packs(pack_paths),1):
        version_out=out/f"version-{number:04d}";version_out.mkdir(exist_ok=True)
        material=local(root,group["material_path"])
        if not material:
            raise ValueError("冻结材料树不存在: "+group["material_path"])
        tree=load(material)
        if tree.get("run") and tree["run"]!=group["material_run"]:
            raise ValueError("材料树和材料包版本不同")
        manifest={"profile":PROFILE,"material_run":group["material_run"],"material_path":group["material_path"],"coordinate_format":"xyxy",
            "pages":{},"files":{},"sources":{}}
        for sid,source in group["sources"].items():
            manifest["sources"][sid]={"id":sid,"type":source["type"],"source":source["source"],"asset":source.get("asset"),"page_ids":[],"file_ids":[],"locations":[],
                "sentences":{sentence_id:_sentence_record(sentence) for sentence_id,sentence in source["sentences"].items()}}
            for sentence_id,sentence in source["sentences"].items():
                if sentence.get("evidence_kind")=="material_index":
                    manifest["sources"][sid]["sentences"][sentence_id].update(status="material_index",reason="这是材料结构索引，保留索引身份，不把它当作原件中的句子")
        prepare_pdf(root,group,version_out,manifest)
        prepare_web(root,group,version_out,manifest,tree)
        prepare_code(root,group,version_out,manifest)
        prepare_assets(root,group,manifest)
        prepare_image_text(root,group,version_out,manifest)
        for sid,source in group['sources'].items():
            for sentence_id,sentence in source['sentences'].items():
                if 'original_variants'in sentence:
                    result=manifest['sources'][sid]['sentences'][sentence_id]
                    result['original_variants']=sentence['original_variants']
                    if sentence.get('location_conflict'):
                        result.update(status='ambiguous',rects=[],reason='同一旧编号保留了不同原文，保留各原始片段及原页，不冒充唯一定位')
        counts=Counter(s["status"] for source in manifest["sources"].values() for s in source["sentences"].values())
        manifest["summary"]={"source_count":len(manifest["sources"]),"sentence_statuses":dict(counts),"page_count":len(manifest["pages"]),"file_count":len(manifest["files"])}
        save(version_out/"manifest.json",manifest)
        index["versions"].append({"material_run":group["material_run"],"material_path":group["material_path"],"manifest":url(root,version_out/"manifest.json"),"summary":manifest["summary"]})
    save(out/"index.json",index)
    return index


def main():
    parser=argparse.ArgumentParser(description="为当前案例的实际材料准备句子位置，不修改原件与材料包")
    parser.add_argument("--root",type=Path,required=True)
    parser.add_argument("--source-pack",type=Path,action="append",default=[])
    parser.add_argument("--pack-directory",type=Path)
    parser.add_argument("--out",type=Path)
    args=parser.parse_args()
    packs=args.source_pack+list(args.pack_directory.glob("*/source-pack.json") if args.pack_directory else [])
    if not packs:
        parser.error("需要提供实际材料包或包含各节材料包的目录")
    print(json.dumps(prepare_locations(args.root,packs,args.out),ensure_ascii=False))


if __name__=="__main__":
    main()
