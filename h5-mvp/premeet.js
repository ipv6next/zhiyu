const $=s=>document.querySelector(s);
let room=null,busy=false,offset=0;
const params=new URLSearchParams(location.search),id=params.get('id'),actor=params.get('actor')||ZhiyuDemo.actor;
function refreshNavigation(){const href=ZhiyuDemo.query('matches.html',{actor});const back=$('#back-link'),resultBack=$('#result-back');if(back)back.href=href;if(resultBack)resultBack.href=href;}
function refreshOpening(name){
  const opening=document.querySelector('#chat > .message');
  if(opening) opening.innerHTML=`<small>${name} · AI 分身 · 开场说明</small>你好，我来和你聊聊。日常问题我会按已有资料、偏好和相处方式回应；没提及的内容会标注“（本人未提及）”，重要决定留到之后由真人交流。你想从哪里聊起？`;
}
function renderMatchmakerTip(guide){
  let box=$('#matchmaker-tip');
  if(!box){box=document.createElement('div');box.id='matchmaker-tip';box.className='matchmaker-tip';$('#stage').after(box);}
  box.replaceChildren();
  const title=document.createElement('b');title.textContent='AI 红娘实时建议';
  const detail=document.createElement('span');detail.textContent=guide.matchmaker_tip||'先从一个具体问题开始，听听彼此的真实表达。';
  box.append(title,detail);
}
async function request(action,extra={}){
  const response=await fetch('/api/room',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,actor,action,...extra})});
  const data=await response.json();if(!response.ok)throw Error(data.error||'连接失败');return data;
}
function error(e){$('#error').hidden=false;$('#error').textContent=e.message||String(e);}
function render(){
  if(room.viewer_role&&room.viewer_role!=='candidate'){error(Error('此入口仅供候选真人进行预会面。'));return;}
  const name=room.member_profile_snapshot?.nickname||'对方';
  document.querySelector('h1').textContent=`与${name}的 AI 分身聊聊`;
  refreshOpening(name);
  const topics=room.premeet_priority_topics||[];const note=$('#priority-note');note.hidden=!topics.length;note.textContent=topics.length?`本次会优先了解：${topics.map(item=>item.category||item.label).join('、')}。` : '';
  const guide=room.conversation_guide||{};$('#stage').textContent=guide.stage?`当前交流节奏：${guide.stage}。以下只是引子，可自由提问。`:'';renderMatchmakerTip(guide);const topicBox=$('#topics');if(guide.prompts?.length){topicBox.replaceChildren();guide.prompts.forEach(prompt=>{const button=document.createElement('button');button.type='button';button.textContent=prompt;topicBox.append(button);});}
  $('#error').hidden=true;$('#rounds').textContent=`${room.rounds} / 20 轮`;$('#progress').value=room.rounds;
  $('#mode').textContent=room.mode==='demo'?'演示模式 · 规则回复，尚未连接大模型':'DeepSeek 模式 · 使用虚构授权档案';
  $('#messages').replaceChildren();
  for(const m of room.messages){const el=document.createElement('div');el.className='message'+(m.role==='user'?' me':'');const label=document.createElement('small');label.textContent=m.role==='user'?'你':`${name} · AI 分身`;el.append(label,document.createTextNode(m.content));$('#messages').append(el);}
  const ended=room.status==='ended';$('#chat').hidden=ended;$('#result').hidden=!ended;
  $('#reason').textContent=`${room.reason} · 完成 ${room.rounds} 轮问答。以下为话题记录，不是 AI 匹配结论。`;
  $('#summary').replaceChildren();const questions=room.messages.filter(m=>m.role==='user');
  for(const q of questions.length?questions:[{content:'本次没有完成问答，尚无足够交流信息。'}]){const li=document.createElement('li');li.textContent=q.content;$('#summary').append(li);}
  const names={true:'愿意继续',false:'暂不继续',null:'尚未决定'};
  $('#decision').textContent=`你：${names[room.decisions.me]}；会员本人：${names[room.decisions.owner]}。`;
  $('#unlocked').hidden=!room.unlocked;tick();
}
async function act(action,extra={}){
  if(busy)return false;busy=true;document.querySelectorAll('button').forEach(b=>b.disabled=true);
  try{room=await request(action,extra);offset=room.server_time*1000-Date.now();render();return true;}catch(e){error(e);return false;}finally{busy=false;document.querySelectorAll('button').forEach(b=>b.disabled=false);}
}
function tick(){if(!room)return;let left=Math.max(0,Math.ceil(room.deadline-(Date.now()+offset)/1000));$('#clock').textContent=room.status==='ended'?'预会面已结束':`剩余 ${[Math.floor(left/3600),Math.floor(left%3600/60),left%60].map(n=>String(n).padStart(2,'0')).join(':')}`;$('#input').disabled=left===0||room.status==='ended';if(!left&&room.status==='active'&&!busy)act('state');}
$('#composer').onsubmit=async e=>{e.preventDefault();const text=$('#input').value.trim();if(!text)return;if(await act('message',{text})){$('#input').value='';$('#messages').lastElementChild?.scrollIntoView({behavior:'smooth',block:'center'});}};
$('#topics').onclick=e=>{if(e.target.tagName==='BUTTON'){$('#input').value=e.target.textContent;$('#input').focus();}};
$('#end').onclick=async()=>{if(confirm('结束后不能继续本次 AI 预会面，确定查看结果吗？')&&await act('end'))location.href='result.html?id='+encodeURIComponent(id)+'&actor='+encodeURIComponent(actor);};
if(location.protocol==='file:')error(Error('请通过 http://127.0.0.1:4180/ 打开本地服务。'));
else if(!id||!actor)error(Error('请从候选推荐页申请 AI 预会面。'));
else {refreshNavigation();act('state');}
setInterval(tick,1000);setInterval(()=>{if(room&&room.status==='active'&&!busy)act('state');},30000);
