import { createContext } from 'preact';
import { useContext } from 'preact/hooks';

export const HostContext=createContext<any>(null);
export function useActiveNoteContext(){return useContext(HostContext);}
export function useContentElement(context:any){return context?.contentElement??null;}
export function useTextEditor(){return null;}
