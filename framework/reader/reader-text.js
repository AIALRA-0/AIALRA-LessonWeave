/* 渲染已有文字与公式，换行和公式标记只影响显示，不修改正文及来源记录 */
window.ReaderText = (() => {
  const base = new URL('.', document.currentScript.src);
  let ready;
  function katexReady() {
    if (!ready) ready = new Promise((resolve, reject) => {
      if (!document.getElementById('lw-katex-css')) {
        const link = document.createElement('link'); link.id = 'lw-katex-css'; link.rel = 'stylesheet';
        link.href = new URL('media-vendor/katex/dist/katex.min.css', base); document.head.append(link);
      }
      if (window.katex) return resolve();
      const script = document.createElement('script'); script.src = new URL('media-vendor/katex/dist/katex.min.js', base);
      script.onload = resolve; script.onerror = reject; document.head.append(script);
    });
    return ready;
  }
  async function math(node, value, display = false) {
    value = window.LessonMath.normalize(value);
    node.classList.add('reader-math'); node.dataset.mathSource = value;
    node.textContent = value;
    if (window.LessonMath.isCode(value)) {
      node.classList.add('reader-code-expression');node.dataset.expressionKind='code';return;
    }
    await katexReady();
    display ||= /\\tag\b/.test(value);
    const prepared=window.LessonMath.prepare(value,source=>{try{window.katex.renderToString(source,{displayMode:display,throwOnError:true,trust:false,strict:'ignore'});return null;}catch(error){return error.message;}});
    value=prepared.source;node.dataset.mathSource=value;
    if(prepared.changed)node.dataset.mathRepair='validated';
    if(prepared.error){node.dataset.mathError=prepared.error;node.classList.add('reader-math-unresolved');return;}
    window.katex.render(value, node, {displayMode: display, throwOnError: false, trust: false, strict: 'ignore'});
    const error=node.querySelector('.katex-error');if(error){node.dataset.mathError=error.title;node.classList.add('reader-math-unresolved');node.textContent=value;}
  }
  function rich(node, value, symbols = [], protectedRanges = []) {
    const text = String(value ?? ''), parsed = window.LessonMath.scan(text, symbols);
    const allowed=part=>!protectedRanges.some(range=>part.start<range.end&&part.end>range.start);
    const parts = [...parsed.matches.filter(allowed).map(match => ({...match, kind:'math'})),
      ...parsed.protected.filter(part => part.code&&allowed(part)).map(part => ({...part, kind:'code'}))].sort((a,b) => a.start-b.start);
    let at = 0;
    for (const part of parts) {
      node.append(document.createTextNode(text.slice(at,part.start)));
      const raw = text.slice(part.start,part.end);
      if (part.kind === 'code') {
        const code=document.createElement('code');code.textContent=raw.replace(/^(`{3,}|~{3,})[^\n]*\n|(?:`{3,}|~{3,})$/g,'').replace(/^`+|`+$/g,'');node.append(code);
      } else if (!part.declared&&/[\u4e00-\u9fff]/.test(part.source.replace(/\\(?:text|mathrm)\{[^}]*\}/g,''))) {
        node.append(document.createTextNode(raw));
      } else {
        const span=document.createElement('span');span.className='reader-math';span.dataset.mathRaw=raw;span.textContent=raw;node.append(span);
        span.mediaReady=(async()=>{
          await katexReady();
          await math(span,part.source,part.display);
          if(!span.dataset.mathError)span.dataset.mathRendered='true';else {span.textContent=raw;if(!part.declared){span.dataset.mathCandidate=span.dataset.mathSource;span.dataset.mathReason=span.dataset.mathError;delete span.dataset.mathError;span.classList.remove('reader-math-unresolved','reader-math');}}
        })().catch(error=>{span.dataset.mathError=error.message;span.classList.add('reader-math-unresolved');span.textContent=raw;});
      }
      at=part.end;
    }
    node.append(document.createTextNode(text.slice(at)));
    return node;
  }
  const mathSkip='pre,code,script,style,textarea,input,select,svg,math,.katex,.reader-math,[data-math-candidate],[contenteditable="true"],[data-no-math]';
  function contextProtection(symbols = []) {
    // 词条会拆开文本节点，命令行的保护范围仍按所在段落或单元格完整读取
    const contexts=new Map();
    return text=>{
      const context=text.parentElement?.closest('p,td,th,li,figcaption,summary');if(!context)return [];
      if(!contexts.has(context)){
        const parsed=window.LessonMath.scan(context.textContent,symbols),offsets=new WeakMap();
        const ranges=parsed.protected.filter(part=>!parsed.matches.some(match=>match.declared&&match.start<part.start&&part.start<match.end));
        if(ranges.length){const nodes=document.createTreeWalker(context,NodeFilter.SHOW_TEXT);let at=0;while(nodes.nextNode()){offsets.set(nodes.currentNode,at);at+=nodes.currentNode.nodeValue.length;}}
        contexts.set(context,{ranges,offsets});
      }
      const {ranges,offsets}=contexts.get(context),at=offsets.get(text);if(at===undefined)return [];
      return ranges.filter(part=>part.start<at+text.nodeValue.length&&part.end>at).map(part=>({start:Math.max(0,part.start-at),end:Math.min(text.nodeValue.length,part.end-at)}));
    };
  }
  function renderIn(element, symbols = []) {
    if (!element) return Promise.resolve();
    const pending=[...element.querySelectorAll('.reader-math')].map(node=>node.mediaReady).filter(Boolean);
    for(const node of element.querySelectorAll('.math-tex,[data-lw-formula]')) {
      if(node.querySelector('.katex'))continue;
      node.mediaReady=math(node,node.dataset.mathSource||node.textContent,true);pending.push(node.mediaReady);
    }
    const walker=document.createTreeWalker(element,NodeFilter.SHOW_TEXT,{
      acceptNode:node=>node.parentElement?.closest(mathSkip)?NodeFilter.FILTER_REJECT:NodeFilter.FILTER_ACCEPT
    });
    const texts=[];while(walker.nextNode())texts.push(walker.currentNode);
    const protectedContext=contextProtection(symbols);
    for(const text of texts) {
      const protectedRanges=protectedContext(text);
      if(!window.LessonMath.scan(text.nodeValue,symbols).matches.some(part=>!protectedRanges.some(range=>part.start<range.end&&part.end>range.start)))continue;
      const fragment=document.createDocumentFragment();rich(fragment,text.nodeValue,symbols,protectedRanges);
      for(const node of fragment.querySelectorAll('.reader-math'))if(node.mediaReady)pending.push(node.mediaReady);
      text.replaceWith(fragment);
    }
    return Promise.all(pending.map(promise=>Promise.resolve(promise).catch(()=>{})));
  }
  function audit(element) {
    const errors=[...element.querySelectorAll('[data-math-error]')].map(node=>({source:node.dataset.mathSource||node.dataset.mathRaw||node.textContent,error:node.dataset.mathError}));
    const walker=document.createTreeWalker(element,NodeFilter.SHOW_TEXT,{acceptNode:node=>node.parentElement?.closest(mathSkip)?NodeFilter.FILTER_REJECT:NodeFilter.FILTER_ACCEPT}),protectedContext=contextProtection();
    while(walker.nextNode()){
      const ranges=protectedContext(walker.currentNode);
      for(const match of window.LessonMath.scan(walker.currentNode.nodeValue).matches)if(match.declared&&!ranges.some(range=>match.start<range.end&&match.end>range.start))errors.push({source:match.source,error:'公式已经有标记，但当前位置还没有渲染'});
    }
    return {rendered:element.querySelectorAll('.katex').length,errors};
  }
  function plain(element) {
    if(element.nodeType===3)return element.nodeValue;
    if(element.classList?.contains('reader-math'))return element.dataset.mathRaw||element.dataset.mathSource||element.textContent;
    return [...element.childNodes].map(plain).join('');
  }
  // 已有分号和句末标点提供安全断点，显示拆段时保留每个原字符
  function paragraphs(text) {
    const source=String(text??'');
    const protectedRanges=value=>{
      const parsed=window.LessonMath.scan(value);
      return [...parsed.matches.filter(part=>part.declared),...parsed.protected.filter(part=>part.code)].sort((a,b)=>a.start-b.start);
    };
    // 完整公式和代码中的换行继续留在原片段里，不能先拆成不成对的标记
    const ranges=protectedRanges(source),pieces=[];let at=0,rangeIndex=0;
    for(let i=0;i<source.length;i++){
      while(ranges[rangeIndex]?.end<=i)rangeIndex++;
      if(ranges[rangeIndex]?.start<=i)continue;
      if(/[\n\r\u2028\u2029]/.test(source[i])){
        pieces.push(source.slice(at,i));if(source[i]==='\r'&&source[i+1]==='\n')i++;at=i+1;
      }
    }
    pieces.push(source.slice(at));
    return pieces.flatMap(part => {
      if (part.length < 300) return [part];
      const result = [],protectedParts=protectedRanges(part);let start=0,index=0;
      for (let i = 0; i < part.length; i++) {
        while(protectedParts[index]?.end<=i)index++;
        if(protectedParts[index]?.start<=i)continue;
        if(i-start>=180&&/[；。]/.test(part[i])){result.push(part.slice(start,i+1));start=i+1;}
      }
      if (start < part.length) result.push(part.slice(start));
      return result;
    }).filter(s => s.trim());
  }
  return {rich, math, paragraphs, renderIn, audit, plain};
})();
