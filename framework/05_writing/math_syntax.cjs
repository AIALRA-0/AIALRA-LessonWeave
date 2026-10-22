/* 用阅读器实际采用的 KaTeX 检查排版语法，只提出确定的文本标识转义，不改原产物 */
const fs=require('fs');
const katex=require(process.argv[2]);
const mathText=require('../reader/math-text.js');
const input=JSON.parse(fs.readFileSync(process.argv[3],'utf8'));
const started=performance.now();
function parse(tex){try{katex.renderToString(tex,{displayMode:true,throwOnError:true,strict:'ignore',trust:false});return null;}catch(error){return error.message;}}
const candidates=input.flatMap(part=>{
  const mixedLabel=part.inline_math_label&&mathText.mixedLabel(part.math);
  if(part.text===undefined&&!mixedLabel)return [part];
  const text=part.text??part.math;
  return mathText.scan(text).matches.map(match=>({...part,text,math:match.source,start:match.start,end:match.end,declared:match.declared,display:match.display}));
});
const results=candidates.filter(part=>part.text===undefined||part.declared||!/[\u4e00-\u9fff]/.test(part.math.replace(/\\(?:text|mathrm)\{[^}]*\}/g,''))).map(part=>{
  const tex=mathText.normalize(part.math);
  if(mathText.isCode(tex))return {...part,error:null,deterministic_fix:null,expression_kind:'code'};
  const prepared=mathText.prepare(tex,parse),error=prepared.originalError||prepared.error;
  const fixed=prepared.changed?prepared.source:null;
  return {...part,error:part.text!==undefined&&!part.declared?null:error,deterministic_fix:fixed&&part.text!==undefined&&part.declared?(part.display?'\\['+fixed+'\\]':'\\('+fixed+'\\)'):fixed};
});
fs.writeFileSync(process.argv[4],JSON.stringify({seconds:(performance.now()-started)/1000,checked:results.length,errors:results.filter(r=>r.error),results}));
