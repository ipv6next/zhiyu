(() => {
  const $ = (s) => document.querySelector(s);
  const mask = $('#name-mask');
  const accountMask = $('#account-mask');
  const error = $('#error');
  const accountError = $('#account-error');
  const go = (user) => { ZhiyuDemo.setActor(user.id); location.href = ZhiyuDemo.query('profile.html',{actor:user.id}); };
  $('#start').onclick = async () => {
    if (ZhiyuDemo.session) {
      try { const r=await fetch('/api/auth',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'me'})}); const d=await r.json(); if(!r.ok) throw Error(); go(d.user); return; } catch (_) { ZhiyuDemo.clear(); }
    }
    mask.hidden=false; setTimeout(()=>$('#nickname').focus(),100);
  };
  document.querySelectorAll('[data-close-name]').forEach((b)=>b.onclick=()=>{mask.hidden=true;error.hidden=true;});
  $('#create').onclick=async()=>{
    try { const r=await fetch('/api/auth',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'local_register',nickname:$('#nickname').value})});const d=await r.json();if(!r.ok)throw Error(d.error||'暂时无法创建账户');ZhiyuDemo.setSession(d);go(d.user); }
    catch(e){error.hidden=false;error.textContent=e.message||'暂时无法创建账户';}
  };
  $('#nickname').addEventListener('keydown',(e)=>{if(e.key==='Enter')$('#create').click();});
  document.querySelectorAll('[data-close-account]').forEach((b)=>b.onclick=()=>{accountMask.hidden=true;accountError.hidden=true;});
  $('#existing-account').onclick=async()=>{
    accountMask.hidden=false; accountError.hidden=true;
    const list=$('#account-list'); list.innerHTML='<p>正在读取已有账号…</p>';
    try {
      const r=await fetch('/api/auth',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'local_accounts'})});
      const d=await r.json(); if(!r.ok) throw Error(d.error||'暂时无法读取已有账号');
      if(!d.accounts.length){list.innerHTML='<p>还没有已注册的本机测试账号。可先点击“马上开始”创建一个。</p>';return;}
      list.innerHTML='';
      d.accounts.forEach((account)=>{
        const button=document.createElement('button'); button.type='button'; button.className='account-option';
        const label=account.membership_active?'会员':'普通用户';
        button.innerHTML=`<b>${account.nickname}</b><small>${label} · ${account.account_status}</small>`;
        button.disabled=account.account_status!=='正常';
        button.onclick=async()=>{
          accountError.hidden=true; button.disabled=true; button.querySelector('small').textContent='正在进入…';
          try {
            const response=await fetch('/api/auth',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'local_login',user_id:account.id})});
            const data=await response.json(); if(!response.ok) throw Error(data.error||'暂时无法登录该账号');
            ZhiyuDemo.clear(); ZhiyuDemo.setSession(data); go(data.user);
          } catch(e) { button.disabled=false; button.querySelector('small').textContent=`${label} · ${account.account_status}`; accountError.hidden=false;accountError.textContent=e.message||'暂时无法登录该账号'; }
        };
        list.appendChild(button);
      });
    } catch(e) { list.innerHTML=''; accountError.hidden=false;accountError.textContent=e.message||'暂时无法读取已有账号'; }
  };
  // Local demo identities must not inherit the prior real login session.
  $('#member-demo').onclick=()=>{ZhiyuDemo.clear();go({id:'demo_member'});};
  $('#candidate-demo').onclick=()=>{ZhiyuDemo.clear();go({id:'demo_candidate'});};
})();
