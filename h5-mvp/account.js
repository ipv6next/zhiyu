(()=>{
  const $=s=>document.querySelector(s),actor=ZhiyuDemo.actor;let accountState=null;
  const notice=value=>{$('#notice').textContent=value;clearTimeout(window.noticeTimer);window.noticeTimer=setTimeout(()=>{$('#notice').textContent=''},2600)};
  const call=async action=>{const r=await fetch('/api/account',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,actor})}),d=await r.json();if(!r.ok)throw Error(d.error||'操作失败');return d;};
  const link=(id,path)=>{$('#'+id).href=ZhiyuDemo.query(path)};
  const localProfile=()=>{try{return JSON.parse(localStorage.getItem('zhiyu-profile:'+actor)||'{}')}catch(_){return {}}};
  const profileProgress=data=>['gender','birthday','height','education','city','marital'].filter(key=>data[key]).length;
  const promotions=[
    {title:'知遇 · 精准匹配',description:'把合适的人带到你面前',action:'开始匹配',path:'service.html',tone:'match'},
    {title:'知遇 · 关系观察',description:'让匹配建议更贴近你的期待',action:'去看看',path:'service.html',tone:'observe'},
    {title:'数字分身预会面',description:'让 AI 先帮你打开一段对话',action:'了解分身',path:'twin.html',tone:'twin'}
  ];
  let promotionIndex=0;
  const renderPromotion=()=>{const item=promotions[promotionIndex],link=$('#promo-link');$('#promo-title').textContent=item.title;$('#promo-description').textContent=item.description;$('#promo-action').textContent=item.action;link.href=ZhiyuDemo.query(item.path);link.dataset.tone=item.tone;$('#promo-dots').querySelectorAll('i').forEach((dot,index)=>dot.classList.toggle('active',index===promotionIndex));};
  async function load(){
    if(!ZhiyuDemo.session){location.href='index.html';return;}
    try{
      const [me,likes]=await Promise.all([call('me'),call('likes')]);
      const account=me.account,profile=me.public||{},draft=localProfile();accountState=account;
      const name=profile.nickname||account.nickname||'知遇用户';
      $('#nickname').textContent=name;$('#avatar').textContent=name.slice(0,1);$('#account-id').textContent='知遇 ID：'+account.id.slice(-8).toUpperCase();
      $('#role-badge').textContent=account.role==='member'?'知遇会员':'知遇用户';
      const completed=profileProgress(draft),meta=[profile.age_range,profile.city].filter(Boolean).join(' · ');
      $('#profile-meta').textContent=meta||`已完成 ${completed}/6 项基础资料`;
      const verification='待认证';
      $('#verify-badge').textContent=verification;$('#verify-copy').textContent=verification;
      $('#liked').textContent=likes.likes?.length||0;$('#liked-by').textContent='—';$('#premeet-count').textContent=account.role==='member'?'查看':'—';
      ['edit-profile','shortcut-profile'].forEach(id=>link(id,'profile.html'));
      if(account.role==='member')$('#revoke').hidden=false;
    }catch(error){notice(error.message||'暂时无法读取账户');}
  }
  $('#settings-top').onclick=()=>$('#settings').click();
  $('#settings').onclick=()=>{const panel=$('#privacy-panel');panel.hidden=!panel.hidden;if(!panel.hidden)panel.scrollIntoView({behavior:'smooth',block:'nearest'});};
  $('#verify').onclick=()=>notice('完成基础资料与照片核验后，可申请资料认证。');
  $('#spotlight').onclick=()=>notice('聚光计划将在推荐排序能力接入后开放。');
  $('#gift').onclick=()=>notice('脱单大礼包将在正式运营活动中开放。');
  $('#share').onclick=()=>notice('邀请功能将在微信能力接入后开放。');
  $('#vip').onclick=()=>{if(accountState?.role==='member'){location.href=ZhiyuDemo.query('member.html');return;}notice('开通会员后，可进入会员中心建立数字分身并完成相处方式题。');};
  $('#revoke').onclick=async()=>{if(!confirm('确认撤销 AI 预会面授权？正在进行的预会面将结束。'))return;try{await call('revoke_premeet');$('#revoke').disabled=true;notice('已撤销 AI 预会面授权。')}catch(error){notice(error.message);}};
  $('#delete').onclick=async()=>{if(!confirm('确认注销并删除账户资料？此操作不可恢复。'))return;try{await call('delete_account');ZhiyuDemo.clear();location.href='index.html';}catch(error){notice(error.message);}};
  renderPromotion();setInterval(()=>{promotionIndex=(promotionIndex+1)%promotions.length;renderPromotion()},4200);load();
})();
