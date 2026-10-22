// 把原生 ReadWeave 面板与薄宿主接口编在一起，业务组件不另写一份
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
const here=path.dirname(fileURLToPath(import.meta.url));
const source=path.resolve(process.argv[2]||process.env.READWEAVE_SOURCE||path.join(here,'source'));
const require=createRequire(path.join(source,'package.json'));
const {build}=require('esbuild');
for(const name of ['native-chunks','native-assets']){
 const output=path.resolve(here,name);
 if(path.dirname(output)!==here)throw Error('Generated asset directory must stay inside the integration directory');
 fs.rmSync(output,{recursive:true,force:true});
}
const client=path.join(source,'apps/client/src');
const alias={
 '@readweave/Panel':path.join(client,'widgets/sidebar/ReadWeavePanel.tsx'),
 '@triliumnext/commons':path.join(source,'packages/commons/src/index.ts'),
 '@triliumnext/ckeditor5':path.join(source,'packages/ckeditor5/src/plugins/readweave_anchor.ts')
};
const result=await build({entryPoints:[path.join(here,'host/entry.tsx')],outdir:here,entryNames:'native-panel',chunkNames:'native-chunks/[name]-[hash]',assetNames:'native-assets/[name]-[hash]',loader:{'.woff2':'file','.woff':'file','.ttf':'file','.eot':'file','.svg':'file'},bundle:true,splitting:true,format:'esm',target:'es2022',jsx:'automatic',jsxImportSource:'preact',minify:true,metafile:true,define:{document:'hostDocument',window:'hostWindow',glob:'hostGlob','process.env.NODE_ENV':'"production"'},inject:[path.join(here,'host/globals.ts')],nodePaths:[path.join(source,'node_modules'),path.join(source,'apps/client/node_modules')],alias,plugins:[{name:'host-adapter',setup(build){
 build.onResolve({filter:/services\/(?:server|i18n|utils)(?:\.js)?$/},args=>{
  const name=path.basename(args.path,'.js');return{namespace:'host-services',path:name};
 });
 build.onLoad({filter:/.*/,namespace:'host-services'},args=>{
  if(args.path==='server')return{contents:`export {default} from ${JSON.stringify(path.join(here,'host/server.ts'))}`,loader:'ts',resolveDir:here};
  if(args.path==='utils')return{contents:'export const randomString=(length)=>Array.from(crypto.getRandomValues(new Uint8Array(length)),v=>"abcdefghijklmnopqrstuvwxyz0123456789"[v%36]).join("");export const isMobile=()=>false,isDesktop=()=>false,isMac=()=>false;export default {randomString,isMobile,isDesktop,isMac}',loader:'js'};
  const language=path.join(client,'translations/cn/translation.json');return{contents:`import i18next from 'i18next';import data from ${JSON.stringify(language)};const i=i18next.createInstance();i.init({lng:'cn',resources:{cn:{translation:data}},initAsync:false});export const t=i.t.bind(i);`,loader:'ts',resolveDir:path.join(source,'apps/client')};
 });
 build.onResolve({filter:/RightPanelWidget(?:\.js)?$/},()=>({path:path.join(here,'host/widget.tsx')}));
 build.onResolve({filter:/(?:^|\/)react\/hooks(?:\.js)?$/},()=>({path:path.join(here,'host/hooks.tsx')}));
 build.onResolve({filter:/react\/(?:ActionButton|Button)(?:\.js)?$/},()=>({path:path.join(here,'host/button.tsx')}));
 }}]});
fs.writeFileSync(path.join(here,'native-build.json'),JSON.stringify({schemaVersion:1,inputFiles:Object.keys(result.metafile.inputs).map(p=>{const absolute=path.resolve(p);return absolute.startsWith(source)?path.relative(source,absolute).replaceAll('\\','/'):'host/'+path.basename(p)}),outputs:Object.fromEntries(Object.entries(result.metafile.outputs).map(([p,value])=>[path.relative(here,path.resolve(p)).replaceAll('\\','/'),value.bytes]))},null,2));
console.log(JSON.stringify({outputs:Object.keys(result.metafile.outputs).map(p=>path.basename(p))}));
