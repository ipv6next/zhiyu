const $=s=>document.querySelector(s);
const actor=ZhiyuDemo.actor;
const api=async data=>{const r=await fetch('/api/account',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const d=await r.json();if(!r.ok)throw Error(d.error||'暂时无法读取数据');return d};
const withActor=path=>ZhiyuDemo.query(path,{actor});
function refreshLinks(){[['#back-link','account.html'],['#twin-link','twin.html'],['#questions-link','twin.html'],['#matches-link','matches.html'],['#nav-discover','matches.html']].forEach(([s,p])=>{const e=$(s);if(e)e.href=withActor(p)});}
function text(tag,value){const node=document.createElement(tag);node.textContent=value;return node;}
function renderRights(rights){
  const box=$('#rights-card');box.replaceChildren();
  const top=document.createElement('div');top.className='rights-top';
  top.append(text('b',rights.membership_active?'会员预会面权益':'普通用户预会面权益'));
  const badge=text('span',rights.membership_active?'会员 ¥98/月':'普通用户');badge.className=rights.membership_active?'member-badge':'normal-badge';top.append(badge);box.append(top);
  const count=document.createElement('div');count.className='rights-count';
  count.innerHTML=rights.membership_active?`<strong>${rights.membership_remaining}</strong><span>本月剩余 / ${rights.member_monthly_quota} 次有效 AI 预会面</span>`:`<strong>${rights.trial_remaining+rights.single_remaining}</strong><span>${rights.trial_remaining?'首场体验可用':'可用单次权益'}${rights.single_remaining?` · 单次 ${rights.single_remaining} 次`:''}</span>`;box.append(count);
  box.append(text('p',rights.charge_rule));
  const foot=document.createElement('div');foot.className='rights-foot';foot.append(text('span',rights.membership_active?'含数字分身、更多推荐与喜欢我的解锁':'首次预会面体验免费；后续 9.9 元/次有效启动'));
  if(!rights.membership_active){const button=document.createElement('a');button.href=withActor('service.html');button.textContent='了解会员权益';foot.append(button)}box.append(foot);
  $('#member-role').textContent=rights.membership_active?'会员视角':'普通用户视角';
  $('#hero-title').textContent=rights.membership_active?'我的 AI 预会面':'先试一次 AI 预会面';
  $('#hero-copy').textContent=rights.membership_active?'你可以浏览推荐并邀请候选真人；对方接受后才有效启动并扣减额度。':'浏览会员资料后可主动进入对方已授权的 AI 分身；你的首场有效预会面可免费体验。';
}
function renderRooms(rooms){const box=$('#rooms'),empty=$('#empty');box.replaceChildren();empty.hidden=true;if(!rooms.length){empty.textContent='还没有预会面。可先浏览推荐，选择想进一步了解的人。';empty.hidden=false;return;}rooms.forEach(room=>{const card=document.createElement('article');card.className='room-card';const candidate=room.candidate_profile_snapshot||{};const status=room.status==='awaiting_candidate'?'等待对方接受':room.status==='active'?'进行中':room.status==='declined'?'对方暂未接受':'已结束';card.append(text('span',status));card.lastChild.className='room-status '+(room.status==='active'?'live':'');card.append(text('h3',candidate.nickname||'候选真人'));card.append(text('p',[candidate.age_range,candidate.city,candidate.relationship_goal].filter(Boolean).join(' · ')||'等待资料完善'));const copy=room.status==='awaiting_candidate'?'对方接受前，不生成聊天记录，也不扣减本次权益。':room.status==='active'?`正在进行 ${room.rounds||0} / 20 轮交流。`:(room.reason||'预会面已结束')+` · 已完成 ${room.rounds||0} 轮。`;card.append(text('p',copy));const link=document.createElement('a');link.href=room.status==='active'?`premeet.html?id=${encodeURIComponent(room.id)}&actor=${encodeURIComponent(actor)}`:`result.html?id=${encodeURIComponent(room.id)}&actor=${encodeURIComponent(actor)}`;link.textContent=room.status==='active'?'继续查看':'查看回顾';card.append(link);box.append(card);});}
async function load(){if(!actor){location.href='index.html';return}refreshLinks();try{const rights=await api({action:'premeet_rights',actor});renderRights(rights);if(rights.membership_active){const data=await api({action:'member_rooms',actor});renderRooms(data.rooms||[])}else renderRooms([])}catch(error){$('#rights-card').textContent=error.message;$('#empty').textContent='暂时无法读取预会面状态';$('#empty').hidden=false;}}
load();
