(() => {
  const params = new URLSearchParams(location.search);
  const supplied = params.get('actor');
  const stored = localStorage.getItem('zhiyu-actor') || localStorage.getItem('zhiyu-demo-actor');
  const session=localStorage.getItem('zhiyu-session') || '';
  // A real login session wins over a URL parameter. This keeps the displayed
  // account aligned with the account the server authenticates.
  const actor = session ? (stored || '') : (supplied || stored || '');
  if (supplied && !session) localStorage.setItem('zhiyu-actor', supplied);
  const nativeFetch=window.fetch.bind(window);
  window.fetch=(input,init={})=>{
    if(session && typeof input==='string' && input.startsWith('/api/') && init.body && typeof init.body==='string'){
      try{const body=JSON.parse(init.body);if(!body.session){body.session=session;init={...init,body:JSON.stringify(body)};}}catch(_){}
    }
    return nativeFetch(input,init);
  };
  window.ZhiyuDemo = {
    actor,
    session,
    setActor(id) { localStorage.setItem('zhiyu-actor', id); },
    setSession(data) { localStorage.setItem('zhiyu-session',data.session);localStorage.setItem('zhiyu-actor',data.user.id); },
    query(path, extra = {}) {
      const target = new URL(path, location.href);
      const id = extra.actor || actor;
      if (id) target.searchParams.set('actor', id);
      Object.entries(extra).forEach(([key, value]) => { if (key !== 'actor' && value != null) target.searchParams.set(key, value); });
      return target.pathname.split('/').pop() + target.search;
    },
    go(path, extra = {}) { location.href = this.query(path, extra); },
    clear() { localStorage.removeItem('zhiyu-demo-actor');localStorage.removeItem('zhiyu-actor');localStorage.removeItem('zhiyu-session'); }
  };
})();
