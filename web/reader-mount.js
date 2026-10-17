(() => {
  const config=window.LESSONWEAVE;
  window.LWPath=value=>{const text=String(value||'');if(!text||/^(https?:|data:|blob:|#)/.test(text)||text.startsWith(config.base+'/'))return text;return config.base+'/'+text.replace(/^\/+/, '')};
  const original=window.fetch.bind(window);
  window.fetch=(input,options)=>original(typeof input==='string'&&/^\/(0[0-5]_)/.test(input)?window.LWPath(input):input,options);
})();
