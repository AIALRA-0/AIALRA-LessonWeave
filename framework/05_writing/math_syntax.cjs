/* 用阅读器实际采用的 KaTeX 检查排版语法，只提出确定的文本标识转义，不改原产物 */
const fs=require('fs');
const katex=require(process.argv[2]);
const input=JSON.parse(fs.readFileSync(process.argv[3],'utf8'));
const started=performance.now();
function parse(tex){try{katex.renderToString(tex,{throwOnError:true,strict:'ignore',trust:false});return null;}catch(error){return error.message;}}
const results=input.map(part=>{
  const tex=part.math.trim().replace(/^\\\(([\s\S]*)\\\)$/,'$1').replace(/^\\\[([\s\S]*)\\\]$/,'$1').replace(/^\$\$([\s\S]*)\$\$$/,'$1');
  const error=parse(tex);
  let proposed=tex.replace(/\\texttt\{([^{}]*)\}/g,(_,inner)=>'\\texttt{'+inner.replace(/(?<!\\)_/g,'\\_')+'}');
  if(/^\$[^$]+\$$/.test(proposed))proposed=proposed.slice(1,-1);
  const pieces=proposed.split(/(?<!\\)\\[\[\]]/g).map(x=>x.trim()).filter(Boolean);
  if(pieces.length>1&&pieces.every(x=>x.trim()))proposed='\\begin{gathered}\n'+pieces.map(x=>x.trim()).join('\\\\\n')+'\n\\end{gathered}';
  return {...part,error,deterministic_fix:error&&proposed!==tex&&!parse(proposed)?proposed:null};
});
fs.writeFileSync(process.argv[4],JSON.stringify({seconds:(performance.now()-started)/1000,checked:results.length,errors:results.filter(r=>r.error),results}));
