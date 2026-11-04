const $=s=>document.querySelector(s),actor=ZhiyuDemo.actor;
async function account(data){const r=await fetch('/api/account',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...data,actor})}),b=await r.json();if(!r.ok)throw Error(b.error||'暂时无法处理');return b;}
async function room(data){const r=await fetch('/api/room',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...data,actor})}),b=await r.json();if(!r.ok)throw Error(b.error||'暂时无法发起');return b;}
function line(value){const p=document.createElement('p');p.textContent=value;return p;}
async function removeLike(target,card){try{await account({action:'recommendation_feedback',target_id:target,status:'cleared'});card.remove();if(!$('#likes').children.length)$('#empty').hidden=false;}catch(e){alert(e.message);}}
async function startPremeet(target,button,isMember){button.disabled=true;try{const r=await room(isMember?{action:'invite',candidate_id:target}:{action:'request',member_id:target});if(isMember)ZhiyuDemo.go('member.html');else ZhiyuDemo.go('premeet.html',{id:r.id});}catch(e){button.disabled=false;button.textContent=e.message;}}
function card(item,isMember){const p=item.profile,card=document.createElement('article');card.className='result-card saved-match';
 const eyebrow=document.createElement('span');eyebrow.className='eyebrow';eyebrow.textContent=item.interaction?.mutual_interest?'双方想进一步了解':'已收藏';card.append(eyebrow);
 const name=document.createElement('h2');name.textContent=p.nickname||item.user.nickname;card.append(name);
 card.append(line([p.age_range,p.city,p.relationship_goal].filter(Boolean).join(' · ')||'已保存的推荐资料'));
 if(item.interaction?.mutual_interest)card.append(line('对方也表示愿意进一步了解，可以由你决定是否发起预会面。'));
 const actions=document.createElement('div');actions.className='saved-match-actions';
 const remove=document.createElement('button');remove.className='saved-remove';remove.textContent='移出喜欢';remove.onclick=()=>removeLike(item.user.id,card);
 const begin=document.createElement('button');begin.className='saved-begin';begin.textContent=isMember?'邀请 AI 预会面':'让 AI 分身先聊聊';begin.onclick=()=>startPremeet(item.user.id,begin,isMember);actions.append(remove,begin);card.append(actions);return card;}
async function load(){if(!actor){location.href='index.html';return;}try{const [me,data]=await Promise.all([account({action:'me'}),account({action:'likes'})]);const isMember=me.account.role==='member';if(!data.likes?.length){$('#empty').hidden=false;return;}data.likes.forEach(item=>$('#likes').append(card(item,isMember)));}catch(e){$('#empty').hidden=false;$('#empty').textContent=e.message;}}
load();
