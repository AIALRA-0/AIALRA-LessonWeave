let transport:(path:string,options?:RequestInit)=>Promise<any>;
export function setTransport(value:typeof transport){transport=value;}
function request(method:string,path:string,payload?:unknown){return transport(path,{method,headers:{'Content-Type':'application/json'},...(payload!==undefined?{body:JSON.stringify(payload)}:{})});}
export default {
 get:<T>(path:string)=>request('GET',path) as Promise<T>,
 getWithSilentNotFound:<T>(path:string)=>request('GET',path) as Promise<T>,
 post:<T>(path:string,payload:unknown)=>request('POST',path,payload) as Promise<T>,
 put:<T>(path:string,payload:unknown)=>request('PUT',path,payload) as Promise<T>,
 patch:<T>(path:string,payload:unknown)=>request('PATCH',path,payload) as Promise<T>,
 remove:<T>(path:string,payload?:unknown)=>request('DELETE',path,payload) as Promise<T>
};
