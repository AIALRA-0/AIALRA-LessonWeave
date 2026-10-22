/* 浏览器和批量检查共用这些识别规则，原文字符和来源位置继续保留 */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.LessonMath = api;
})(typeof window === 'object' ? window : globalThis, function () {
  const escape = text => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const letter = '[A-Za-z\u0370-\u03ff]';
  const group0 = '\\{[^{}\\n]*\\}', group1 = '\\{(?:[^{}\\n]|' + group0 + ')*\\}';
  const group = '\\{(?:[^{}\\n]|' + group1 + ')*\\}';
  const par0 = '\\([^()\\n]*\\)', par = '\\((?:[^()\\n]|' + par0 + ')*\\)';
  const sub = '(?:' + group + '|' + letter + '[A-Za-z0-9\u0370-\u03ff]*|[0-9]+)';
  const command = '\\\\[A-Za-z]+(?:\\[[^\\]\\n]*\\])?(?:' + group + ')*';
  const base = '(?:' + command + '|' + group + '|' + par + '|[0-9]+(?:\\.[0-9]+)?|(?:id|dim|rank|ker|det|sin|cos|tan|log|ln|lim)(?![A-Za-z])|' + letter + '(?![A-Za-z\u0370-\u03ff]))';
  const atom = base + '(?:[_^]' + sub + '|[⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺ⁿ₀₁₂₃₄₅₆₇₈₉₋₊]+)*(?:' + par + ')?!?';
  const op = '(?:<=|>=|!=|:=|[=+*/×÷−≤≥≈≠<>∘∈∉⊂⊆⊃⊇∩∪→↦←↔≃≅≡]|-(?=[^A-Za-z]|' + letter + '(?![A-Za-z]))|\\\\(?:circ|times|cdot|div|leq?|geq?|approx|neq?|in|notin|to|mapsto|subseteq?|supseteq?|cap|cup|cong|simeq)\\b)';
  const expression = new RegExp('(?<![A-Za-z0-9_/:.\\\\])(?:' + atom + '(?:[ \\t]*' + op + '[ \\t]*' + atom + ')+|' + command + '(?:[_^]' + sub + ')*|' + letter + '(?:[_^]' + sub + '|[⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺ⁿ₀₁₂₃₄₅₆₇₈₉₋₊]+)(?:' + par + ')?|[0-9]+!(?!=|[A-Za-z0-9_]))(?![A-Za-z0-9_/:.])', 'g');
  const explicit = /\$\$([\s\S]+?)\$\$|(?<![\\$])\$(?!\$)([^$\n]+?)\$(?![$A-Za-z_])|(?<!\\)(\\{1,2})\(([\s\S]+?)\3\)|(?<!\\)(\\{1,2})\[([\s\S]+?)\5\]|\\begin\{(equation\*?|align\*?|aligned|alignedat|gather\*?|gathered|multline\*?|split|matrix|pmatrix|bmatrix|Bmatrix|vmatrix|Vmatrix|cases|array)\}[\s\S]*?\\end\{\7\}/g;
  const protectedText = /(`{3,}|~{3,})[^\n]*\n[\s\S]*?\1|(`+)(?!`)[\s\S]*?\2(?!`)|https?:\/\/[^\s<>]+|\b[A-Za-z]:[\\/][^\s<>]+|(?:^|\s)(?:\.{0,2}\/)[\w./-]+|\$\{[^}]+\}|\$(?:past|stable|rose|fell|isunknown|clog2)\b|\$[A-Z_]{2,}[A-Z0-9_]*(?![A-Za-z0-9_$=+*/^<>-])|(?<!\\)\$\d+(?:\.\d+)?(?=[\s，,；;]|$)|\b[\w-]+\.(?:py|v|sv|js|ts|json|md|pdf|png|jpr|cpp|h|html|css)\b/g;
  const unicode = { '∘': '\\circ ', '→': '\\to ', '↦': '\\mapsto ', '←': '\\leftarrow ', '↔': '\\leftrightarrow ', '∈': '\\in ', '∉': '\\notin ', '⊂': '\\subset ', '⊆': '\\subseteq ', '⊃': '\\supset ', '⊇': '\\supseteq ', '∩': '\\cap ', '∪': '\\cup ', '−': '-', '≤': '\\leq ', '≥': '\\geq ', '≠': '\\neq ', '≈': '\\approx ', '×': '\\times ', '÷': '\\div ', '≃': '\\simeq ', '≅': '\\cong ', '≡': '\\equiv ' };
  const superscripts={'⁰':'0','¹':'1','²':'2','³':'3','⁴':'4','⁵':'5','⁶':'6','⁷':'7','⁸':'8','⁹':'9','⁻':'-','⁺':'+','ᵃ':'a','ᵇ':'b','ᶜ':'c','ᵈ':'d','ᵉ':'e','ᶠ':'f','ᵍ':'g','ʰ':'h','ⁱ':'i','ʲ':'j','ᵏ':'k','ˡ':'l','ᵐ':'m','ⁿ':'n','ᵒ':'o','ᵖ':'p','ʳ':'r','ˢ':'s','ᵗ':'t','ᵘ':'u','ᵛ':'v','ʷ':'w','ˣ':'x','ʸ':'y','ᶻ':'z'};
  function normalize(value) {
    let text = String(value ?? '').trim();
    text = text.replace(/^(\\{1,2})\(([\s\S]*)\1\)$/, '$2').replace(/^(\\{1,2})\[([\s\S]*)\1\]$/, '$2')
      .replace(/^\$\$([\s\S]*)\$\$$/, '$1').replace(/^\$([^$\n]+)\$$/, '$1');
    // 文字命令里的原字符保持原样，只规范数学部分的 Unicode 运算符
    return text.split(/(\\(?:text|texttt|textrm|mathrm|operatorname)\{[^{}]*\})/g).map((part, index) => index % 2 ? part : part
      .replace(/[∘→↦←↔∈∉⊂⊆⊃⊇∩∪−≤≥≠≈×÷≃≅≡]/g, char => unicode[char])
      .replace(/[⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻ]+/g, value => '^{'+[...value].map(char => superscripts[char]).join('')+'}')
      .replace(/[₀₁₂₃₄₅₆₇₈₉₋₊]+/g, value => '_{'+[...value].map(char=>char==='₋'?'-':char==='₊'?'+':'₀₁₂₃₄₅₆₇₈₉'.indexOf(char)).join('')+'}')
      .replace(/(?<![A-Za-z0-9_^\\{])id(?=[_^])/g, '\\operatorname{id}')).join('');
  }
  function mixedLabel(value) {
    const text=String(value??'');
    return scan(text).matches.some(match=>match.declared)||/[\u4e00-\u9fff]/.test(text.replace(/\\(?:text|texttt|textrm|mathrm|operatorname)\{[^{}]*\}/g,''));
  }
  function isCode(value) {
    const layout=/\\begin\{(?:align|array|[pPbBvV]?matrix|cases|gather|split|multline)/.test(value);
    return (!layout&&/(?<!\\)&/.test(value)) || /\$(?:past|stable|rose|fell|isunknown|clog2)\b|##/.test(value)
      || (!/\\[A-Za-z]/.test(value)&&/\b[A-Za-z][A-Za-z0-9]+_[A-Za-z0-9_]+\b/.test(value)&&/\b[A-Za-z][A-Za-z0-9]{2,}\s*\(/.test(value));
  }
  function declarations(text) {
    const result = [...String(text).matchAll(/(?<![A-Za-z0-9_])([A-Za-z\u0370-\u03ff](?:_[A-Za-z0-9\u0370-\u03ff]{1,3})?)(?=表示|代表|标记|记作)/g)].map(match => match[1]);
    result.push(...[...String(text).matchAll(/第([ijkmn])个|(?:节点总数|节点数|总数|数量)([A-Za-z])(?=[\u4e00-\u9fff])/g)].map(match => match[1] || match[2]));
    return result;
  }
  function prepare(value, validate) {
    const source=normalize(value);
    const error=validate(source);
    if(!error)return {source,error:null,changed:false};
    let proposed=source.replace(/\\texttt\{([^{}]*)\}/g,(_,inner)=>'\\texttt{'+inner.replace(/(?<!\\)_/g,'\\_')+'}');
    proposed=proposed.replace(/\\\{([^{}]*?)(?<!\\)\}/g,'\\{$1\\}');
    const pieces=proposed.split(/(?<!\\)\\[\[\]]/g).map(part=>part.trim()).filter(Boolean);
    if(pieces.length>1)proposed='\\begin{gathered}\n'+pieces.join('\\\\\n')+'\n\\end{gathered}';
    if(proposed!==source&&!validate(proposed))return {source:proposed,error:null,changed:true,originalError:error};
    return {source,error,changed:false};
  }
  function symbols(values) {
    const greek={alpha:'α',beta:'β',gamma:'γ',delta:'δ',epsilon:'ε',zeta:'ζ',eta:'η',theta:'θ',iota:'ι',kappa:'κ',lambda:'λ',mu:'μ',nu:'ν',xi:'ξ',pi:'π',rho:'ρ',sigma:'σ',tau:'τ',phi:'φ',chi:'χ',psi:'ψ',omega:'ω',Gamma:'Γ',Delta:'Δ',Theta:'Θ',Lambda:'Λ',Xi:'Ξ',Pi:'Π',Sigma:'Σ',Phi:'Φ',Psi:'Ψ',Omega:'Ω'};
    return [...new Set(values.flatMap(value => typeof value === 'string' ? [value.trim().replace(/\\([A-Za-z]+)/g,(raw,name)=>greek[name]||raw)] : []))]
      .filter(value => /^[A-Za-z\u0370-\u03ff](?:[_^](?:[A-Za-z0-9\u0370-\u03ff]+|\{[^{}]+\}))*$/.test(value)).sort((a, b) => b.length - a.length);
  }
  function scan(value, known = []) {
    const text = String(value ?? ''), found = [], protectedSpans = [];
    const overlaps = (start, end, rows) => rows.some(row => start < row.end && end > row.start);
    for (const match of text.matchAll(protectedText)) protectedSpans.push({ start: match.index, end: match.index + match[0].length, code: /^[`~]/.test(match[0]) });
    // 花括号里的首尾锚点属于正则表达式，美元符号不参与公式配对
    for (const match of text.matchAll(/\{\^[^{}\n]*\$\}/g)) protectedSpans.push({start:match.index,end:match.index+match[0].length,code:false});
    // 命令提示符所在的整行作为代码保留，行尾闭合的美元公式继续按公式读取
    for(const match of text.matchAll(/(?:^|\n)[ \t]*\$[ \t]+[A-Za-z][\w.-]*[ \t]+[^\n]+/g))if(!match[0].trimEnd().endsWith('$'))protectedSpans.push({start:match.index,end:match.index+match[0].length,code:false});
    const add = (start, end, source, display = false, declared = false) => {
      if (!overlaps(start, end, protectedSpans) && !overlaps(start, end, found)) found.push({ start, end, source: normalize(source), display, declared });
    };
    for (const match of text.matchAll(explicit)) {
      const source = match[1] ?? match[2] ?? match[4] ?? match[6] ?? match[0];
      add(match.index, match.index + match[0].length, source, !!(match[1] || match[6] || match[7]), true);
    }
    // 已经声明的公式先整体保留，snake_case 只在普通文字中作为代码标识保护
    const identifiers = [...text.matchAll(/\b[A-Za-z][A-Za-z0-9]+_[A-Za-z0-9_]+\b/g)].map(match => ({ start: match.index, end: match.index + match[0].length }));
    for (const match of text.matchAll(expression)) {
      if (overlaps(match.index, match.index + match[0].length, identifiers) && !/(?:∘|\\(?:circ|operatorname)\b)/.test(match[0])) continue;
      if (/^[A-Za-z]\s*[<>]\s*[A-Za-z]$/.test(match[0]) && !/数学|比较|变量|满足|条件/.test(text)) continue;
      add(match.index, match.index + match[0].length, match[0]);
    }
    const local = symbols([...known, ...declarations(text)]);
    if (local.length) {
      const regex = new RegExp('(?<![A-Za-z0-9_/:.\\\\])(?:' + local.map(escape).join('|') + ')(?![A-Za-z0-9_/:.])', 'g');
      for (const match of text.matchAll(regex)) add(match.index, match.index + match[0].length, match[0]);
    }
    return { matches: found.sort((a, b) => a.start - b.start), protected: protectedSpans };
  }
  return { normalize, declarations, symbols, scan, prepare, isCode, mixedLabel };
});
