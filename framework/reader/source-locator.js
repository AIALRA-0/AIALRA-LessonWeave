// 当前位置从当前章节的真实材料包读取，原句、译句和原件共用材料版本与句子编号
(() => {
  const $ = id => document.getElementById(id);
  const surface = $('locator-surface'), viewport = $('locator-viewport'), image = $('locator-image'), iframe = $('locator-dom');
  if (!surface || !viewport || !iframe) return;
  image.hidden = true;
  let tileLayer=null,tileObserver=null,tileKey=null;
  function showRaster(page) {
    const key=page?.tiles?.length?page.image:null;
    if(key&&key===tileKey){image.hidden=true;tileLayer.setAttribute('aria-label',image.alt);return;}
    tileObserver?.disconnect();tileObserver=null;tileLayer?.remove();tileLayer=null;tileKey=key;
    if(!key)return;
    image.removeAttribute('src');image.hidden=true;
    tileLayer=make('div');tileLayer.setAttribute('role','img');tileLayer.setAttribute('aria-label',image.alt);
    Object.assign(tileLayer.style,{position:'relative',width:'100%',aspectRatio:page.width+' / '+page.height});
    tileObserver=new IntersectionObserver((entries,observer)=>{
      for(const entry of entries)if(entry.isIntersecting){const el=entry.target;if(el.isConnected)el.src=el.dataset.tile;observer.unobserve(el);}
    },{root:viewport,rootMargin:'64px'});
    for(const tile of page.tiles){
      const el=make('img'),[left,top,right,bottom]=tile.bbox;el.alt='';el.draggable=false;el.decoding='async';
      el.dataset.tile=window.LWPath?window.LWPath(tile.image):tile.image;
      Object.assign(el.style,{position:'absolute',left:left/page.width*100+'%',top:top/page.height*100+'%',
        width:(right-left)/page.width*100+'%',height:(bottom-top)/page.height*100+'%',maxWidth:'none',margin:'0'});
      tileLayer.append(el);tileObserver.observe(el);
    }
    image.after(tileLayer);
  }
  let manifest, sourcePack, pending, selection, selectedId, normalId, normalSentenceId, savedView;
  let mode = 'page', fit = 'highlight', positions = [], currentPage, currentSource, currentRefs = [], currentFile;
  let domLoaded = false, activeSentenceId = null, eligibleSentences = [], hoverTimer, documentGeneration = 0, currentPageId;
  let materialIdentity = null, initialFit = true;
  const zoom = { page: 1, dom: 1 };
  const originalDOMWidths = new WeakMap(), panDocuments = new WeakSet();
  const zoomKey = 'aialra:source-zoom:v1';
  try { const saved = Number(localStorage.getItem(zoomKey)); if (saved >= 10 && saved <= 300) zoom.page = zoom.dom = saved / 100; } catch {}
  let recenterFrame = 0, pendingCenter = false, pendingFit = false, pendingAnchor = null, savedDOMView = null;
  let domHighlights = null, domFit = null, domSize = null, navigationKey = '', viewOptionsKey = '';
  // 只有选句、回到高亮或主动适配会居中，加载和尺寸变化保留自由拖动的位置
  function scheduleRecenter(center = true, fitOnce = false, anchor = null) {
    fitOnce ||= initialFit && center;
    pendingCenter ||= center; pendingFit ||= fitOnce; if (anchor) pendingAnchor = anchor;
    if (!recenterFrame) recenterFrame = requestAnimationFrame(() => {
      recenterFrame = 0;
      const options = { center: pendingCenter, fitOnce: pendingFit, anchor: pendingAnchor };
      pendingCenter = false; pendingFit = false; pendingAnchor = null; recenter(options);
    });
  }
  const make = (tag, text, cls) => { const el = document.createElement(tag); if (text) el.textContent = text; if (cls) el.className = cls; return el; };
  const sourceFor = id => sourcePack?.sources.find(source => source.id === id);
  const locationFor = id => manifest?.sources?.[id];
  const refsFor = id => selection?.refs.filter(ref => ref.source_id === id) || [];
  const setStatus = text => { $('locator-status').textContent = text; $('locator-view-select').title = text; };
  const sentenceFor = () => currentSource?.sentences?.find(sentence => sentence.id === activeSentenceId);
  function sentenceLocation() {
    const sentence = sentenceFor(), result = locationFor(selectedId)?.sentences?.[activeSentenceId];
    // 句子编号相同而原文不同的时候，旧位置保持失效，不会借用旧坐标
    return result && sentence && result.original === sentence.original ? result : null;
  }
  function bounds() {
    const location = locationFor(selectedId);
    if (activeSentenceId) { const sentence = sentenceLocation(); return (sentence?.status === 'exact' ? sentence.rects : []).filter(rect => rect.page_id === currentPageId).map(rect => rect.bbox); }
    const sourceBoxes = (location?.locations || []).filter(item => item.page_id === currentPageId).map(item => item.bbox);
    if (!sourceBoxes.length) return [];
    const requested = new Set(currentRefs.flatMap(ref => ref.region_ids || []).map(id => id.split('.')[0]));
    const regions = sourcePack.image_regions?.[selectedId];
    const childBoxes = [...requested].map(name => regions?.[name]).filter(Boolean);
    if (!childBoxes.length) return sourceBoxes;
    const box = sourceBoxes[0];
    return childBoxes.map(region => {
      const [x, y, width, height] = region.bbox, [iw, ih] = region.image_size;
      return [box[0] + x / iw * (box[2] - box[0]), box[1] + y / ih * (box[3] - box[1]),
        box[0] + (x + width) / iw * (box[2] - box[0]), box[1] + (y + height) / ih * (box[3] - box[1])];
    });
  }
  function validBox(box, page) {
    return box?.length === 4 && box.every(Number.isFinite) && box[2] > box[0] && box[3] > box[1] &&
      box[0] >= 0 && box[1] >= 0 && box[2] <= page.width + 1 && box[3] <= page.height + 1;
  }
  function drawPage() {
    positions = currentPage ? bounds().filter(box => validBox(box, currentPage)) : [];
    $('locator-highlights').replaceChildren(...positions.map(box => {
      const el = make('span', null, 'locator-highlight');
      el.dataset.sourceId = selectedId; if (activeSentenceId) el.dataset.sentenceId = activeSentenceId;
      el.dataset.materialRun = sourcePack.material_run; el.dataset.materialPath = sourcePack.material_path;
      el.dataset.bbox = JSON.stringify(box);
      el.setAttribute('aria-label', (activeSentenceId || selectedId) + ' 在原件中的位置');
      Object.assign(el.style, { left: box[0] / currentPage.width * 100 + '%', top: box[1] / currentPage.height * 100 + '%',
        width: (box[2] - box[0]) / currentPage.width * 100 + '%', height: (box[3] - box[1]) / currentPage.height * 100 + '%' });
      return el;
    }));
    if (currentPage) {
      image.style.aspectRatio = currentPage.width + ' / ' + currentPage.height;
      image.alt = (currentPage.number ? 'PDF 第 ' + currentPage.number + ' 页' : currentPage.kind === 'image' ? '原始图片' : '当前离线网页的原页') + '，来源 ' + selectedId;
      showRaster(currentPage);
      if(!currentPage.tiles?.length){
        image.onload = () => scheduleRecenter(false);
        const imagePath = window.LWPath ? window.LWPath(currentPage.image) : currentPage.image; if (image.getAttribute('src') !== imagePath) image.src = imagePath;
        image.hidden = false;
      }
    } else { showRaster(null);image.removeAttribute('src'); image.hidden = true; }
    scheduleRecenter();
  }
  function union(boxes) {
    return boxes.length ? [Math.min(...boxes.map(box => box[0])), Math.min(...boxes.map(box => box[1])),
      Math.max(...boxes.map(box => box[2])), Math.max(...boxes.map(box => box[3]))] : null;
  }
  function captureView() {
    if (mode === 'dom' || currentFile) {
      const doc = iframe.contentDocument;
      if (!domLoaded || !doc?.body || !iframe.clientWidth) return null;
      const rect = doc.body.getBoundingClientRect(), scale = Number(doc.body.style.zoom) || 1;
      return { kind: 'dom', x: (iframe.clientWidth / 2 - rect.left) / scale, y: (iframe.clientHeight / 2 - rect.top) / scale };
    }
    if (!currentPage || !viewport.clientWidth) return null;
    const page = $('locator-page').getBoundingClientRect(), area = viewport.getBoundingClientRect(), scale = page.width / currentPage.width;
    return scale ? { kind: 'page', x: (area.left + viewport.clientWidth / 2 - page.left) / scale, y: (area.top + viewport.clientHeight / 2 - page.top) / scale } : null;
  }
  function setZoom(percent, schedule = true) {
    if (!Number.isFinite(Number(percent))) return;
    const anchor = schedule ? captureView() : null;
    if (schedule) initialFit = false;
    const value = Math.max(10, Math.min(300, Math.round(Number(percent))));
    zoom.page = zoom.dom = value / 100;
    try { localStorage.setItem(zoomKey, String(value)); } catch {}
    updateZoomUI(); if (schedule) scheduleRecenter(false, false, anchor);
  }
  function recenter(options) {
    const defer = () => { pendingCenter ||= options.center; pendingFit ||= options.fitOnce; if (options.anchor) pendingAnchor = options.anchor; };
    if (mode === 'dom' || currentFile) {
      if (!domLoaded || !iframe.clientWidth || !iframe.clientHeight) { defer(); return; }
      highlightDOM(options); return;
    }
    if (!currentPage || !viewport.clientWidth) { defer(); return; }
    const whole = [0, 0, currentPage.width, currentPage.height], highlight = union(positions);
    const target = fit === 'highlight' && highlight ? highlight : whole;
    const anchor = options.anchor || (!options.center ? captureView() : null);
    if (options.fitOnce) {
      const base = Math.min(Math.max(1, viewport.clientWidth - 24) / (target[2] - target[0]), Math.max(1, viewport.clientHeight - 24) / (target[3] - target[1]));
      setZoom(Math.floor(base * 100), false);
      initialFit = false;
      surface.dataset.initialFitted = 'true';
    }
    const scale = zoom.page, page = $('locator-page'), stage = $('locator-stage');
    page.style.width = currentPage.width * scale + 'px';
    stage.style.width = currentPage.width * scale + 'px';
    stage.style.padding = viewport.clientHeight + 'px ' + viewport.clientWidth + 'px';
    const centered = options.fitOnce ? target : highlight || whole;
    const point = options.center ? { x: (centered[0] + centered[2]) / 2, y: (centered[1] + centered[3]) / 2 } : anchor?.kind === 'page' ? anchor : null;
    if (point) {
      const rect = page.getBoundingClientRect(), area = viewport.getBoundingClientRect();
      viewport.scrollTo({ left: viewport.scrollLeft + rect.left - area.left + point.x * scale - viewport.clientWidth / 2,
        top: viewport.scrollTop + rect.top - area.top + point.y * scale - viewport.clientHeight / 2, behavior: 'instant' });
    }
  }
  function fitDOM(nodes, options) {
    const doc = iframe.contentDocument;
    if (!doc?.body || !iframe.clientWidth || !iframe.clientHeight) return;
    const anchor = options.anchor || (!options.center ? captureView() : null);
    const collect = () => { const boxes = []; for (const node of nodes) {
      let rects;
      if (currentFile) {
        const range = doc.createRange(); range.selectNodeContents(node); rects = [...range.getClientRects()];
        const row = node.getBoundingClientRect();
        if (rects.length) rects.push({ left: row.left, right: Math.min(...rects.map(rect => rect.left)), top: row.top, bottom: row.bottom });
      } else rects = [...node.getClientRects()];
      for (const rect of rects) if (rect.right > rect.left && rect.bottom > rect.top) boxes.push([rect.left, rect.top, rect.right, rect.bottom]);
    } return union(boxes); };
    if (options.fitOnce) {
      const width = iframe.clientWidth, height = iframe.clientHeight;
      const reusable = domFit?.doc === doc && domFit.width === width && domFit.height === height &&
        domFit.nodes.length === nodes.length && nodes.every((node, index) => node === domFit.nodes[index]);
      if (!reusable) {
        // 只有点击适配时才测量原始比例，普通选句沿用已有缩放
        doc.body.style.zoom = 1;
        const box = collect(); if (!box) { doc.body.style.zoom = zoom[mode]; return; }
        domFit = { doc, nodes, width, height, base: Math.min(Math.max(1, width - 24) / (box[2] - box[0]), Math.max(1, height - 24) / (box[3] - box[1])) };
      }
      setZoom(Math.floor(domFit.base * 100), false);
      initialFit = false;
      surface.dataset.initialFitted = 'true';
    }
    doc.body.style.zoom = zoom[mode];
    if (options.center) {
      const actual = collect(); if (!actual) return;
      iframe.contentWindow.scrollTo({ left: iframe.contentWindow.scrollX + (actual[0] + actual[2] - iframe.clientWidth) / 2,
        top: iframe.contentWindow.scrollY + (actual[1] + actual[3] - iframe.clientHeight) / 2, behavior: 'instant' });
    } else if (anchor?.kind === 'dom') {
      const rect = doc.body.getBoundingClientRect();
      iframe.contentWindow.scrollTo({ left: iframe.contentWindow.scrollX + rect.left + anchor.x * zoom[mode] - iframe.clientWidth / 2,
        top: iframe.contentWindow.scrollY + rect.top + anchor.y * zoom[mode] - iframe.clientHeight / 2, behavior: 'instant' });
    }
  }
  function normalizedMap(text) {
    const chars = [], offsets = []; let index = 0;
    for (const char of text) {
      for (let letter of char.normalize('NFKC').toLowerCase()) {
        letter = letter.replace(/[‘’]/g, "'").replace(/[“”]/g, '"').replace(/[–—−]/g, '-').replace(/\u00ad/g, '');
        if (letter && !/\s/u.test(letter)) { chars.push(letter); offsets.push(index); }
      }
      index += char.length;
    }
    return { text: chars.join(''), offsets };
  }
  // 在实际 DOM 文本节点中逐字找回当前句，链接、强调和原始节点继续保留
  function markSentence(root, sentence, sentenceId, allowedRows=null) {
    const nodes = [], walker = root.ownerDocument.createTreeWalker(root, NodeFilter.SHOW_TEXT); let node, raw = '';
    while (node = walker.nextNode()) {
      if (node.parentElement.closest('script,style')) continue;
      if(allowedRows&&!allowedRows.has(node.parentElement.closest('.code-line')))continue;
      nodes.push({ node, start: raw.length }); raw += node.textContent;
    }
    const actual = normalizedMap(raw), needle = normalizedMap(sentence).text, start = actual.text.indexOf(needle);
    if (!needle || start < 0 || actual.text.indexOf(needle, start + 1) >= 0) return false;
    const first = actual.offsets[start], last = actual.offsets[start + needle.length - 1] + 1;
    for (const item of nodes) {
      const a = Math.max(0, first - item.start), b = Math.min(item.node.length, last - item.start);
      if (b <= a) continue;
      const range = root.ownerDocument.createRange(); range.setStart(item.node, a); range.setEnd(item.node, b);
      const mark = root.ownerDocument.createElement('mark'); mark.dataset.locatorMark = 'true'; mark.dataset.sentenceId = sentenceId;
      range.surroundContents(mark);
    }
    return true;
  }
  function highlightDOM(options) {
    if (!domLoaded || !currentSource) return;
    const doc = iframe.contentDocument; if (!doc?.body) return;
    if(currentFile){
      let style=doc.getElementById('lessonweave-code-location-style');
      if(!style){style=doc.createElement('style');style.id='lessonweave-code-location-style';doc.head.append(style);}
      const dark=document.body.dataset.theme==='dark';
      style.textContent='.code-lines{white-space:pre;width:max-content;min-width:100%;margin:0}.code-line{display:block;width:max-content;min-width:100%}.code-line.location-selected{background:transparent!important;outline:0!important}mark[data-locator-mark]{background:'+(dark?'#383838':'#dededb')+';color:inherit;box-shadow:none;outline:none}body{background:'+(dark?'#1e1e1e':'#ffffff')+';color:'+(dark?'#eeeeee':'#232321')+'}';
    }
    if (!options.center && !options.anchor) options = { ...options, anchor: captureView() };
    const width = iframe.clientWidth, height = iframe.clientHeight;
    if (!originalDOMWidths.has(doc.body)) originalDOMWidths.set(doc.body, doc.body.style.width);
    if (domSize?.doc !== doc || domSize.width !== width || domSize.height !== height) {
      Object.assign(doc.documentElement.style, { width: width + 'px', padding: height + 'px ' + width + 'px', boxSizing: 'content-box' });
      doc.body.style.width = originalDOMWidths.get(doc.body); doc.body.style.zoom = 1;
      doc.body.style.width = getComputedStyle(doc.body).width; doc.body.style.zoom = zoom[mode];
      domHighlights = null; domFit = null;
      domSize = { doc, width, height };
    }
    doc.body.style.position = 'relative';
    const key = JSON.stringify([selectedId, activeSentenceId, currentRefs]);
    if (domHighlights?.doc === doc && domHighlights.key === key && domHighlights.nodes.length && domHighlights.nodes.every(node => node.isConnected)) {
      fitDOM(domHighlights.nodes, options); return;
    }
    domFit = null;
    doc.querySelectorAll('[data-locator-mark]').forEach(el => el.replaceWith(...el.childNodes)); doc.body.normalize();
    doc.querySelectorAll('.location-selected').forEach(el => el.classList.remove('location-selected'));
    doc.querySelectorAll('.dom-image-region').forEach(el => el.remove());
    if (currentFile) {
      const location = sentenceLocation();
      if (location?.status !== 'exact' || location.file_id !== currentFile.id) { describe(); return; }
      const rows=new Set();
      for(let line=location.start_line;line<=location.end_line;line++){const row=doc.getElementById('L'+line);if(row)rows.add(row);}
      const quotes=currentRefs.flatMap(ref=>ref.quotes||[]).filter(quote=>quote.sentence_id===activeSentenceId);
      let precise=false;
      for(const quote of quotes)precise=markSentence(doc.querySelector('.code-lines'),quote.text,activeSentenceId,rows)||precise;
      if(!precise){
        for(let line=location.start_line;line<=location.end_line;line++){
          const row=doc.getElementById('L'+line);if(!row)continue;
          const text=row.firstChild;if(!text||text.nodeType!==Node.TEXT_NODE)continue;
          const start=line===location.start_line?location.start_column||0:0;
          const end=line===location.end_line?location.end_column??[...text.textContent].length:[...text.textContent].length;
          const first=[...text.textContent].slice(0,start).join('').length,last=[...text.textContent].slice(0,end).join('').length;
          if(last<=first)continue;
          const range=doc.createRange();range.setStart(text,first);range.setEnd(text,last);
          const mark=doc.createElement('mark');mark.dataset.locatorMark='true';mark.dataset.sentenceId=activeSentenceId;range.surroundContents(mark);
        }
      }
      const nodes=[...doc.querySelectorAll('[data-locator-mark]')];
      domHighlights = { doc, key, nodes }; fitDOM(nodes, options);
      describe(); return;
    }
    let target; try { target = doc.querySelector(currentSource.source.dom_path); } catch {}
    if (!target) { setStatus(selectedId + ' · 当前离线 DOM 没有取得对应节点'); return; }
    let found = false;
    if (activeSentenceId) {
      const sentence = sentenceFor();
      const location = sentenceLocation();
      if (sentence && location?.status === 'exact') {
        if (location.method === 'image_ocr_characters') {
          const img = target.tagName === 'IMG' ? target : target.querySelector('img');
          const sourceBox = locationFor(selectedId)?.locations?.find(item => item.page_id === 'web')?.bbox;
          if (img && sourceBox) {
            const r = img.getBoundingClientRect(), origin = doc.body.getBoundingClientRect(), factor = Number(doc.body.style.zoom) || 1;
            for (const rect of location.rects.filter(rect => rect.page_id === 'web')) {
              const box = rect.bbox, el = doc.createElement('div');
              el.className = 'dom-image-region'; el.dataset.sentenceId = activeSentenceId;
              Object.assign(el.style, { position: 'absolute', pointerEvents: 'none', boxSizing: 'border-box', border: '2px solid #b77714', background: '#e9a73c22',
                left: (r.left - origin.left + (box[0] - sourceBox[0]) / (sourceBox[2] - sourceBox[0]) * r.width) / factor + 'px',
                top: (r.top - origin.top + (box[1] - sourceBox[1]) / (sourceBox[3] - sourceBox[1]) * r.height) / factor + 'px',
                width: (box[2] - box[0]) / (sourceBox[2] - sourceBox[0]) * r.width / factor + 'px',
                height: (box[3] - box[1]) / (sourceBox[3] - sourceBox[1]) * r.height / factor + 'px' });
              doc.body.append(el); found = true;
            }
          }
        } else found = markSentence(target, sentence.original, sentence.id);
      }
    } else {
      target.classList.add('location-selected');
      const regionIds = new Set(currentRefs.flatMap(ref => ref.region_ids || []).map(id => id.split('.')[0]));
      const img = target.tagName === 'IMG' ? target : target.querySelector('img');
      if (img && regionIds.size) {
        // 图片边框会随 DOM 缩放，区域坐标除以当前缩放后再放进同一文档
        const r = img.getBoundingClientRect(), origin = doc.body.getBoundingClientRect(), factor = Number(doc.body.style.zoom) || 1;
        for (const name of regionIds) {
          const region = sourcePack.image_regions?.[selectedId]?.[name]; if (!region) continue;
          const [x, y, width, height] = region.bbox, [iw, ih] = region.image_size, el = doc.createElement('div');
          el.className = 'dom-image-region'; el.dataset.region = name;
          Object.assign(el.style, { position: 'absolute', pointerEvents: 'none', boxSizing: 'border-box', border: '2px solid #b77714', background: '#e9a73c22',
            left: (r.left - origin.left + x / iw * r.width) / factor + 'px', top: (r.top - origin.top + y / ih * r.height) / factor + 'px',
            width: width / iw * r.width / factor + 'px', height: height / ih * r.height / factor + 'px' });
          doc.body.append(el);
        }
      }
    }
    const nodes = found ? [...doc.querySelectorAll('[data-locator-mark],.dom-image-region')] : [...doc.querySelectorAll('.location-selected,.dom-image-region')];
    if (!nodes.length) nodes.push(target);
    domHighlights = { doc, key, nodes }; fitDOM(nodes, options);
    if (activeSentenceId) setStatus(activeSentenceId + ' · ' + (found ? '原句已在实际 DOM 中高亮' : '当前句的精确 DOM 位置尚未取得'));
    else setStatus(selectedId + ' · 已定位实际网页节点');
  }
  function loadDOM(path) {
    path = window.LWPath ? window.LWPath(path) : path;
    if (iframe.getAttribute('src') === path) { if (domLoaded) scheduleRecenter(); return; }
    domLoaded = false; iframe.style.visibility = 'hidden'; iframe.src = window.LWPath ? window.LWPath(path) : path;
  }
  function setMode(next) {
    mode = next === 'dom' && manifest?.web ? 'dom' : 'page';
    const showDOM = mode === 'dom' || !!currentFile;
    viewport.hidden = showDOM; iframe.hidden = !showDOM;
    const choices = currentFile ? [['highlight', currentSource?.type === 'code' || currentSource?.verbatim_code ? '源码行号' : '文件行号']] :
      [['highlight', currentPage?.kind === 'pdf' ? 'PDF 高亮' : currentPage?.kind === 'image' ? '原图高亮' : '原页高亮'], ['page', currentPage?.kind === 'pdf' ? 'PDF 整页' : '完整原页']];
    if (manifest?.web) choices.push(['dom', '网页 DOM']);
    const optionsKey = JSON.stringify(choices);
    if (optionsKey !== viewOptionsKey) {
      $('locator-view-select').replaceChildren(...choices.map(([value, label]) => { const option = make('option', label); option.value = value; return option; }));
      viewOptionsKey = optionsKey;
    }
    $('locator-view-select').value = mode === 'dom' ? 'dom' : currentFile ? 'highlight' : fit;
    updateZoomUI();
    if (showDOM) loadDOM(currentFile ? currentFile.dom : manifest.web.dom);
    else { describe(); scheduleRecenter(); }
  }
  function describe() {
    if (!currentSource) return;
    const sourceKind = currentSource.source?.kind;
    const originalKind = sourceKind === 'html' ? '原网页' : sourceKind === 'pdf' || /\.pdf$/i.test(currentSource.source?.path || '') ? 'PDF 原件' : '原件';
    const location = sentenceLocation(), prefix = currentFile ? currentFile.path : currentPage?.number ? 'PDF 第 ' + currentPage.number + ' 页' : currentPage?.kind === 'image' ? '原图' : originalKind;
    if (activeSentenceId) {
      if (currentFile && location?.status === 'exact') setStatus(activeSentenceId + ' · ' + prefix + ' · 第 ' + location.start_line + '–' + location.end_line + ' 行');
      else setStatus(activeSentenceId + ' · ' + prefix + ' · ' + (positions.length ? '仅高亮当前句' : location?.status === 'ambiguous' ? '原句存在多个相同位置，尚未取得唯一句框' : '当前句的精确坐标尚未取得'));
    } else setStatus(selectedId + ' · ' + prefix + (currentPage ? ' · 原材料位置' : ' · 当前材料尚未取得可显示的原件位置'));
  }
  function sentenceOptions(source, refs) {
    const requested = new Set(refs.flatMap(ref => ref.sentence_ids || []));
    return (source.sentences || []).filter(sentence => sentence.evidence_kind !== 'material_index' && (!requested.size || requested.has(sentence.id)));
  }
  function renderSentenceNavigation() {
    $('locator-sentence-navigation').hidden = !eligibleSentences.length || !activeSentenceId;
    $('locator-page-navigation').hidden = true;
    if (!eligibleSentences.length || !activeSentenceId) return;
    const index = eligibleSentences.findIndex(sentence => sentence.id === activeSentenceId);
    const all = currentSource.sentences.filter(sentence => sentence.evidence_kind !== 'material_index');
    const choice = $('locator-sentence-select');
    const key = JSON.stringify([selectedId, eligibleSentences.map(sentence => sentence.id)]);
    if (key !== navigationKey) {
      const indexes = new Map(all.map((sentence, index) => [sentence.id, index + 1]));
      choice.replaceChildren(...eligibleSentences.map(sentence => {
        const option = make('option', indexes.get(sentence.id) + '/' + all.length);
        option.value = sentence.id; option.title = sentence.original; return option;
      }));
      navigationKey = key;
    }
    choice.value = activeSentenceId; choice.title = sentenceFor()?.original || '';
    $('locator-sentence-label').textContent = '第 ' + (all.findIndex(sentence => sentence.id === activeSentenceId) + 1) + ' / ' + all.length + (currentFile ? ' 段原文' : ' 句');
    $('locator-previous-sentence').disabled = index <= 0; $('locator-next-sentence').disabled = index >= eligibleSentences.length - 1;
    const ids = [...new Set((sentenceLocation()?.rects || []).map(rect => rect.page_id))];
    $('locator-page-navigation').hidden = ids.length < 2;
    $('locator-page-label').textContent = ids.length ? '第 ' + (ids.indexOf(currentPageId) + 1) + ' / ' + ids.length + ' 页' : '';
    $('locator-previous-page').disabled = ids.indexOf(currentPageId) <= 0;
    $('locator-next-page').disabled = ids.indexOf(currentPageId) >= ids.length - 1;
  }
  function revealSentence() {
    const pair = activeSentenceId ? $('source-cards').querySelector('[data-sentence-id="' + CSS.escape(activeSentenceId) + '"]') : null;
    if (!pair) return;
    const pane = $('source-text-scroll'), r = pair.getBoundingClientRect(), area = pane.getBoundingClientRect();
    if (r.top < area.top || r.height > area.height) pane.scrollTop += r.top - area.top - 10;
    else if (r.bottom > area.bottom) pane.scrollTop += r.bottom - area.bottom + 10;
  }
  function selectSource(id, refs = refsFor(id), preferredSentence = null) {
    const source = sourceFor(id); if (!source || !manifest) return;
    const previousKey = JSON.stringify([selectedId, activeSentenceId, currentRefs]);
    eligibleSentences = sentenceOptions(source, refs);
    const candidates = eligibleSentences.map(sentence => sentence.id), previous = id === selectedId ? activeSentenceId : null;
    const requestedSentences = refs.some(ref => ref.sentence_ids?.length);
    const regionOnly = refs.some(ref => ref.region_ids?.length) && !requestedSentences;
    const wholeImage = !!source.asset && ['image', 'figure', 'figure_group'].includes(source.type) && !requestedSentences && !preferredSentence;
    activeSentenceId = (regionOnly && !preferredSentence) || wholeImage ? null : [preferredSentence, previous, ...candidates].find(id => candidates.includes(id)) || null;
    selectedId = id; currentSource = source;
    const selectedSentence = sentenceFor();
    currentRefs = activeSentenceId ? [{ source_id: id, sentence_ids: [activeSentenceId], quotes:refs.flatMap(ref=>ref.quotes||[]).filter(quote=>quote.sentence_id===activeSentenceId), ...(selectedSentence?.region ? { region_ids: [selectedSentence.region] } : {}) }] : refs;
    if (!selection?.block_id) { normalId = id; normalSentenceId = activeSentenceId; }
    const location = sentenceLocation(), sourceLocation = locationFor(id);
    currentFile = location?.file_id ? manifest.files[location.file_id] : null;
    currentPageId = location?.rects?.[0]?.page_id || sourceLocation?.page_ids?.[0];
    currentPage = manifest.pages[currentPageId];
    $('locator-dialog-title').textContent = '原文定位 · ' + id + (currentPage?.number ? ' · 第 ' + currentPage.number + ' 页' : '');
    const sourceSelect = $('locator-source-select');
    if (![...sourceSelect.options].some(option => option.value === id)) { const option = make('option', id); option.value = id; sourceSelect.append(option); }
    sourceSelect.value = id; sourceSelect.title = id;
    const targets = new Set(activeSentenceId ? $('source-cards').querySelectorAll('.source-sentence-pair[data-sentence-id="' + CSS.escape(activeSentenceId) + '"]') : []);
    for (const pair of $('source-cards').querySelectorAll('.is-locator-selected')) if (!targets.has(pair)) { pair.classList.remove('is-locator-selected'); pair.removeAttribute('aria-current'); }
    for (const pair of targets) if (!pair.classList.contains('is-locator-selected')) { pair.classList.add('is-locator-selected'); pair.setAttribute('aria-current', 'true'); }
    if (previousKey === JSON.stringify([selectedId, activeSentenceId, currentRefs])) { renderSentenceNavigation(); scheduleRecenter(); return; }
    drawPage(); describe(); renderSentenceNavigation(); setMode(mode);
  }
  function update(detail) {
    pending = detail; if (!manifest || !sourcePack) return;
    const wasPreview = !!selection?.block_id;
    if (detail.block_id && !wasPreview) savedView = { id: selectedId, sentenceId: activeSentenceId, top: viewport.scrollTop, left: viewport.scrollLeft };
    selection = detail;
    const ids = [...new Set(detail.refs.map(ref => ref.source_id))].filter(id => sourceFor(id));
    $('locator-source-select').replaceChildren(...ids.map(id => { const option = make('option', id); option.value = id; return option; }));
    const locatable = id => { const value=manifest.sources[id]; return value && (value.page_ids?.length || value.file_ids?.length); };
    const preferred = ids.find(locatable) || ids[0];
    const next = detail.block_id ? preferred : ids.includes(normalId) ? normalId : preferred;
    if (!next) { setStatus('当前内容没有可定位的原材料'); return; }
    selectSource(next, refsFor(next), detail.block_id ? null : normalSentenceId);
    if (detail.block_id) revealSentence();
    if (wasPreview && !detail.block_id && savedView && ids.includes(savedView.id)) {
      const restore = savedView; savedView = null; selectSource(restore.id, refsFor(restore.id), restore.sentenceId);
      requestAnimationFrame(() => viewport.scrollTo({ top: restore.top, left: restore.left, behavior: 'instant' }));
    }
  }
  async function documentReady(detail) {
    if (!detail?.sourcePack || !detail.ready) return;
    const generation = ++documentGeneration; sourcePack = detail.sourcePack; manifest = null; initialFit = true;
    navigationKey = ''; domHighlights = null; domFit = null; domSize = null; savedDOMView = null;
    const identity = sourcePack.material_run + '\n' + sourcePack.material_path;
    if (identity !== materialIdentity) { iframe.removeAttribute('src'); domLoaded = false; materialIdentity = identity; }
    selectedId = null; activeSentenceId = null; currentSource = null; currentPage = null; currentFile = null; selection = null;
    image.hidden = true; image.removeAttribute('src'); $('locator-highlights').replaceChildren(); $('locator-source-select').replaceChildren();
    pending = detail.selection; setMode('page'); setStatus('正在读取当前材料的原件位置');
    try {
      const response = await fetch('/05_writing/source-location/index.json', { cache: 'no-store' });
      if (!response.ok) throw new Error('positions unavailable');
      const index = await response.json();
      const version = index.versions.find(item => item.material_run === sourcePack.material_run && item.material_path === sourcePack.material_path);
      if (!version) throw new Error('material version unavailable');
      const locationResponse = await fetch(version.manifest, { cache: 'no-store' });
      if (!locationResponse.ok) throw new Error('positions unavailable');
      const value = await locationResponse.json();
      if (generation !== documentGeneration) return;
      if (value.material_run !== sourcePack.material_run || value.material_path !== sourcePack.material_path) throw new Error('material version mismatch');
      manifest = value; if (pending) update(pending);
    } catch (error) {
      if (generation === documentGeneration) { $('locator-highlights').replaceChildren(); setStatus('当前材料版本的原件位置尚未准备，原句与译句仍可对照'); }
    }
  }
  document.addEventListener('reading:document-ready', event => documentReady(event.detail));
  document.addEventListener('reading:source-selection', event => update(event.detail));
  document.addEventListener('reading:source-focus', event => selectSource(event.detail.source_id));
  function selectPair(pair) {
    const card = pair?.closest('[data-source-id]'); if (!card || !manifest) return;
    // 图组里的图注与图片标签按它们自己的句子编号找回来源
    const source = sourcePack.sources.find(source => source.sentences?.some(sentence => sentence.id === pair.dataset.sentenceId)) || sourceFor(card.dataset.sourceId);
    const sentence = source?.sentences?.find(sentence => sentence.id === pair.dataset.sentenceId); if (!sentence) return;
    selectSource(source.id, refsFor(source.id).length ? refsFor(source.id) : [{ source_id: source.id }], sentence.id);
  }
  $('source-cards').addEventListener('click', event => {
    clearTimeout(hoverTimer); const pair = event.target.closest('[data-sentence-id]');
    if (pair) selectPair(pair); else { const card = event.target.closest('[data-source-id]'); if (card) selectSource(card.dataset.sourceId); }
  });
  $('source-cards').addEventListener('pointerover', event => {
    if (event.pointerType !== 'mouse' || event.buttons) return;
    const pair = event.target.closest('[data-sentence-id]'); if (!pair || pair.contains(event.relatedTarget)) return;
    clearTimeout(hoverTimer); hoverTimer = setTimeout(() => { if (pair.matches(':hover')) selectPair(pair); }, 140);
  });
  $('source-cards').addEventListener('pointerout', event => { const pair = event.target.closest('[data-sentence-id]'); if (pair && !pair.contains(event.relatedTarget)) clearTimeout(hoverTimer); });
  $('source-cards').addEventListener('focusin', event => { const pair = event.target.closest('[data-sentence-id]'); if (pair?.matches(':focus-visible')) selectPair(pair); });
  function stepSentence(amount) {
    const index = eligibleSentences.findIndex(sentence => sentence.id === activeSentenceId), next = eligibleSentences[index + amount];
    if (!next) return; selectSource(selectedId, refsFor(selectedId), next.id); revealSentence();
  }
  $('locator-previous-sentence').onclick = () => stepSentence(-1); $('locator-next-sentence').onclick = () => stepSentence(1);
  $('locator-sentence-select').onchange = event => { selectSource(selectedId, refsFor(selectedId), event.target.value); revealSentence(); };
  $('locator-source-select').onchange = event => { selectSource(event.target.value); revealSentence(); };
  const pageNavigation = make('div', null, 'locator-sentence-navigation'); pageNavigation.id = 'locator-page-navigation'; pageNavigation.hidden = true;
  for (const [id, label, amount] of [['locator-previous-page', '上一页', -1], ['locator-page-label', '', 0], ['locator-next-page', '下一页', 1]]) {
    const element = make(amount ? 'button' : 'span', label, amount ? 'text-action' : ''); element.id = id;
    if (amount) element.onclick = () => {
      const ids = [...new Set((sentenceLocation()?.rects || []).map(rect => rect.page_id))], next = ids[ids.indexOf(currentPageId) + amount];
      if (!next) return; currentPageId = next; currentPage = manifest.pages[next]; drawPage(); describe(); renderSentenceNavigation();
    };
    pageNavigation.append(element);
  }
  surface.before(pageNavigation);
  // 图像与高亮共用同一父元素，缩放时保持原始坐标比例
  function updateZoomUI() {
    const percent = Math.round(zoom[mode] * 100);
    document.querySelectorAll('[data-locator-zoom]').forEach(button => {
      const action = button.dataset.locatorZoom, factor = zoom[mode];
      button.disabled = action === 'out' && factor <= .1 || action === 'in' && factor >= 3;
    });
    document.querySelectorAll('[data-locator-zoom-select]').forEach(select => {
      if (!select.options.length || !select.dataset.ready) {
        const values = [...new Set([...Array.from({length:30},(_,index)=>(index+1)*10),25,75,125,175])].sort((a,b)=>a-b);
        select.replaceChildren(...values.map(value => { const option = make('option', value + '%'); option.value = value; return option; }));
        select.dataset.ready = 'true';
      }
      select.querySelectorAll('[data-custom]').forEach(option => { if (Number(option.value) !== percent) option.remove(); });
      if (![...select.options].some(option => Number(option.value) === percent)) { const option = make('option', percent + '%'); option.value = percent; option.dataset.custom = 'true'; select.append(option); }
      select.value = percent;
    });
    document.querySelectorAll('[data-locator-fit]').forEach(button => button.disabled = mode === 'dom' || currentFile ? !domLoaded : !currentPage);
  }
  document.querySelectorAll('[data-locator-zoom]').forEach(button => button.addEventListener('click', () => {
    const action = button.dataset.locatorZoom;
    setZoom(zoom[mode] * 100 + (action === 'in' ? 10 : -10));
  }));
  document.querySelectorAll('[data-locator-zoom-select]').forEach(select => select.onchange = event => setZoom(event.target.value));
  document.querySelectorAll('[data-locator-fit]').forEach(button => button.onclick = () => scheduleRecenter(true, true));
  $('locator-view-select').onchange = event => { fit = event.target.value === 'page' ? 'page' : 'highlight'; setMode(event.target.value === 'dom' ? 'dom' : 'page'); };
  $('locator-recenter').onclick = () => scheduleRecenter(true);
  function installPan(target, read, write) {
    let drag = null;
    target.style.touchAction = 'none'; target.style.cursor = 'grab';
    target.addEventListener('dragstart', event => event.preventDefault());
    target.addEventListener('pointerdown', event => {
      if (event.button !== 0 || event.target.closest('a,button,input,textarea,select,[contenteditable=true]')) return;
      drag = { id: event.pointerId, x: event.clientX, y: event.clientY, ...read() };
      target.setPointerCapture(event.pointerId); target.style.cursor = 'grabbing'; target.style.userSelect = 'none'; event.preventDefault();
    });
    target.addEventListener('pointermove', event => {
      if (!drag || drag.id !== event.pointerId) return;
      write(drag.left + drag.x - event.clientX, drag.top + drag.y - event.clientY); event.preventDefault();
    });
    const finish = () => { drag = null; target.style.cursor = 'grab'; target.style.userSelect = ''; };
    target.addEventListener('pointerup', finish); target.addEventListener('pointercancel', finish); target.addEventListener('lostpointercapture', finish);
  }
  image.draggable = false;
  installPan(viewport, () => ({ left: viewport.scrollLeft, top: viewport.scrollTop }), (left, top) => viewport.scrollTo(left, top));
  iframe.addEventListener('load', () => {
    domLoaded = true;
    const doc = iframe.contentDocument;
    if (doc?.documentElement && !panDocuments.has(doc)) {
      panDocuments.add(doc);
      installPan(doc.documentElement, () => ({ left: iframe.contentWindow.scrollX, top: iframe.contentWindow.scrollY }), (left, top) => iframe.contentWindow.scrollTo(left, top));
    }
    const restore = savedDOMView; savedDOMView = null;
    if (restore && restore.source === selectedId && restore.sentence === activeSentenceId && restore.path === iframe.getAttribute('src')) scheduleRecenter(false, false, restore.anchor);
    else scheduleRecenter(true);
    updateZoomUI(); iframe.style.visibility = 'visible';
  });
  new ResizeObserver(() => scheduleRecenter(false)).observe(surface);
  document.addEventListener('reading:source-view-change', () => { scheduleRecenter(false); requestAnimationFrame(revealSentence); });
  const dialog = $('locator-dialog'), home = surface.parentNode;
  function prepareDOMMove() { if (iframe.getAttribute('src')) { savedDOMView = { source: selectedId, sentence: activeSentenceId, path: iframe.getAttribute('src'), anchor: captureView() }; domLoaded = false; iframe.style.visibility = 'hidden'; } }
  document.addEventListener('reading:source-view-changing', prepareDOMMove);
  $('locator-expand').onclick = () => { prepareDOMMove(); $('locator-dialog-content').append(surface); dialog.showModal(); scheduleRecenter(false); };
  $('locator-dialog-close').onclick = () => dialog.close();
  dialog.addEventListener('close', () => { prepareDOMMove(); home.insertBefore(surface, $('locator-status')); scheduleRecenter(false); $('locator-expand').focus({ preventScroll: true }); });
  updateZoomUI();
  window.ReaderSourceLocator = {
    state: () => ({ selectedId, sentenceId: activeSentenceId, mode, fit, free: true, zoom: { ...zoom }, blockId: selection?.block_id,
      materialRun: sourcePack?.material_run, materialPath: sourcePack?.material_path, sourceIds: [...new Set(selection?.refs.map(ref => ref.source_id) || [])],
      positions, currentPage, currentFile, status: sentenceLocation()?.status, domLoaded }),
    select: (sourceId, sentenceId) => selectSource(sourceId, refsFor(sourceId), sentenceId)
  };
  const initial = window.ReaderSourceBridge?.getState(); if (initial?.ready) documentReady(initial);
})();
