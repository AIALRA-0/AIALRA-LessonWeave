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
    value = String(value).trim().replace(/^\\\(([\s\S]*)\\\)$/, '$1').replace(/^\\\[([\s\S]*)\\\]$/, '$1').replace(/^\$\$([\s\S]*)\$\$$/, '$1');
    node.classList.add('reader-math'); node.dataset.mathSource = value;
    node.textContent = value;
    const texLayout = /\\begin\{(?:aligned|align|array|matrix|cases)/.test(value);
    if ((!texLayout && /(?<!\\)&/.test(value)) || /\$(?:past|stable|rose|fell|isunknown|clog2)\b|##|_\{[^}]+\}_\{/.test(value)) {
      node.classList.add('reader-code-expression');node.dataset.expressionKind='code';return;
    }
    await katexReady();
    window.katex.render(value, node, {displayMode: display, throwOnError: false, trust: false, strict: 'ignore'});
    const error=node.querySelector('.katex-error');if(error){node.dataset.mathError=error.title;node.classList.add('reader-math-unresolved');node.textContent=value;}
  }
  const escape = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  function symbol(value) { return value.replace(/_([A-Za-z]{2,})(?![A-Za-z{])/g, '_{$1}'); }
  // 只识别有数学语法的候选，普通单词、文件名、源码与货币由外层保留
  const group0='\\{[^{}\\n]*\\}', group1='\\{(?:[^{}\\n]|'+group0+')*\\}', group='\\{(?:[^{}\\n]|'+group1+')*\\}';
  const command='\\\\(?:[A-Za-z]+)(?:\\[[^\\]\\n]*\\])?(?:'+group+')*';
  const atom='(?:'+command+'|'+group+'|[0-9]+(?:\\.[0-9]+)?|[A-Za-z](?![A-Za-z]))(?:[_^](?:'+group+'|[A-Za-z0-9]+))*!?';
  const op='(?:[=+×÷−≤≥≈≠<>]|\\\\(?:times|cdot|div|leq?|geq?|approx|neq?|in|to)\\b)';
  const expression=new RegExp('(?<![A-Za-z0-9_/:.\\\\])(?:'+atom+'(?:[ \\t]*'+op+'[ \\t]*'+atom+')+|'+command+'(?:[_^](?:'+group+'|[A-Za-z0-9]+))*(?:[ \\t]*[A-Za-z](?:[_^](?:'+group+'|[A-Za-z0-9]+))+)?|(?:[A-Za-z]|[0-9]+(?:\\.[0-9]+)?)[_^](?:'+group+'|[A-Za-z0-9]+)|[0-9]+!(?!=|[A-Za-z0-9_]))(?![A-Za-z0-9_/:.])','g');
  function candidates(text,known){
    const found=[];
    const explicit=/\$\$([\s\S]+?)\$\$|(?<!\\)\$([^$\n]+?)\$|\\\(([\s\S]+?)\\\)|\\\[([\s\S]+?)\\\]|\\begin\{(equation\*?|align\*?|aligned|gather\*?|matrix|pmatrix|bmatrix|cases)\}[\s\S]*?\\end\{\5\}/g;
    const add=(start,end,source,display=false,declared=false)=>{if(!found.some(r=>start<r.end&&end>r.start))found.push({start,end,source:symbol(source),display,declared});};
    for(const m of text.matchAll(explicit))add(m.index,m.index+m[0].length,m[1]??m[2]??m[3]??m[4]??m[0],!!(m[1]||m[4]||m[5]),true);
    for(const m of text.matchAll(expression)){
      const value=m[0];
      if(/^[A-Za-z]{2,}$/.test(value)||/^[A-Za-z]\s*[<>]\s*[A-Za-z]$/.test(value)&&!/数学|比较|变量|满足|条件/.test(text))continue;
      if(!/[_^=×÷−≤≥≈≠<>]|\\[A-Za-z]|\d!/.test(value))continue;
      add(m.index,m.index+value.length,value);
    }
    if(known.length){const rx=new RegExp('(?<![A-Za-z0-9_/:.])(?:'+known.map(escape).join('|')+')(?![A-Za-z0-9_/:.])','g');for(const m of text.matchAll(rx))add(m.index,m.index+m[0].length,m[0]);}
    return found.sort((a,b)=>a.start-b.start);
  }
  function rich(node, value, symbols = []) {
    const text = String(value ?? '');
    const declared = [...text.matchAll(/(?<![A-Za-z0-9_])([A-Za-z](?:_[A-Za-z0-9]{1,3})?)(?=表示|代表)/g)].map(m=>m[1]);
    declared.push(...[...text.matchAll(/第([ijkmn])个|(?:节点总数|节点数|总数|数量)([A-Za-z])(?=[\u4e00-\u9fff])/g)].map(m=>m[1]||m[2]));
    const known = [...new Set([...symbols,...declared])].filter(s => /^[A-Za-z](?:_[A-Za-z0-9{}]+)?$/.test(s)).sort((a,b) => b.length-a.length);
    function prose(part) {
      let at = 0;
      for (const match of candidates(part,known)) {
        node.append(document.createTextNode(part.slice(at, match.start)));
        const candidate=match.source;
        if (/[\u4e00-\u9fff]/.test(candidate.replace(/\\(?:text|mathrm)\{[^}]*\}/g,''))) {
          node.append(document.createTextNode(part.slice(match.start,match.end)));at=match.end;continue;
        }
        const span = document.createElement('span');span.className='reader-math';span.textContent=part.slice(match.start,match.end);node.append(span);
        span.mediaReady = (async()=>{
          await katexReady();
          try{window.katex.renderToString(candidate,{throwOnError:true,trust:false,strict:'ignore'});}
          catch(error){span.classList.remove('reader-math');span.dataset.mathCandidate=candidate;span.dataset.mathReason=error.message;span.textContent=part.slice(match.start,match.end);return;}
          await math(span,candidate,match.display);
        })().catch(()=>{span.textContent=part.slice(match.start,match.end)});
        at = match.end;
      }
      node.append(document.createTextNode(part.slice(at)));
    }
    let at = 0;
    for (const protectedPart of text.matchAll(/(`{3,}|~{3,})[^\n]*\n[\s\S]*?\1|(`+)(?!`)[\s\S]*?\2(?!`)|https?:\/\/[^\s<>]+|\$(?:past|stable|rose|fell|isunknown|clog2)\b|\$\{[^}]+\}|\$[A-Z_]{2,}[A-Z0-9_]*(?![A-Za-z0-9_$=+*/^<>-])|(?<!\\)\$\d+(?:\.\d+)?(?=[\s，,；;]|$)|\b[A-Za-z][A-Za-z0-9]+_[A-Za-z0-9_]+\b|\b[\w-]+\.(?:py|v|sv|js|json|md|pdf|png|jpr)\b/g)) {
      prose(text.slice(at,protectedPart.index));
      if(protectedPart[0].startsWith('`')){const code=document.createElement('code');code.textContent=protectedPart[0].replace(/^`+|`+$/g,'');node.append(code);}
      else node.append(document.createTextNode(protectedPart[0]));
      at=protectedPart.index+protectedPart[0].length;
    }
    prose(text.slice(at));
  }
  // 已有分号和句末标点提供安全断点，显示拆段时保留每个原字符
  function paragraphs(text) {
    const pieces = String(text ?? '').split(/\r\n|[\n\r\u2028\u2029]/);
    return pieces.flatMap(part => {
      if (part.length < 300) return [part];
      const result = []; let start = 0;
      for (let i = 0; i < part.length; i++) if (i-start >= 180 && /[；。]/.test(part[i])) {
        result.push(part.slice(start,i+1)); start=i+1;
      }
      if (start < part.length) result.push(part.slice(start));
      return result;
    }).filter(s => s.trim());
  }
  return {rich, math, paragraphs};
})();
