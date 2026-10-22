let root:ShadowRoot|HTMLElement;
const realDocument=globalThis.document;
const realWindow=globalThis.window;
export function setRoot(value:typeof root){root=value;}
export const hostDocument=new Proxy({} as Document,{get(_target,key){
 if(key==='body')return root??realDocument.body;
 if(key==='activeElement')return (root as ShadowRoot)?.activeElement??realDocument.activeElement;
 if(key==='querySelector'||key==='querySelectorAll')return ((root??realDocument) as any)[key].bind(root??realDocument);
 if(key==='getElementById')return (id:string)=>(root??realDocument).querySelector('#'+CSS.escape(id));
 if(key==='addEventListener'||key==='removeEventListener')return (type:string,handler:any,options:any)=>{
  const target=type==='selectionchange'?realDocument:(root??realDocument);return target[key](type,handler,options);
 };
 const value=(realDocument as any)[key];return typeof value==='function'?value.bind(realDocument):value;
}});
export const hostWindow=new Proxy({} as Window,{get(_target,key){
 if(key==='document')return hostDocument;
 if(key==='getSelection')return ()=>typeof (root as any)?.getSelection==='function'?(root as any).getSelection():realWindow.getSelection();
 const value=(realWindow as any)[key];return typeof value==='function'?value.bind(realWindow):value;
}});
export const hostGlob={getComponentByEl:()=>null};
