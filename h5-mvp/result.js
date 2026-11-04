const $=s=>document.querySelector(s);
const params=new URLSearchParams(location.search),id=params.get('id'),actor=params.get('actor')||ZhiyuDemo.actor;
let room=null,busy=false;
function error(message){$('#error').hidden=false;$('#error').textContent=message;}
function render(){
  const isMember=room.viewer_role==='member';
  const back=isMember?ZhiyuDemo.query('member.html',{actor}):ZhiyuDemo.query('matches.html',{actor});
  $('#back-link').href=back;$('#return-link').href=back;$('#return-link').textContent=isMember?'返回会员中心':'返回会员推荐';
  $('#reason').textContent=`${room.reason} · 完成 ${room.rounds} 轮问答。以下只整理本次交流，不替双方作出是否合适的判断。`;
  $('#analysis').textContent=room.result_analysis||'正在整理 AI 红娘的即时建议…';
  $('#analysis-status').textContent=room.analysis_notice || (room.analysis_mode==='deep'?'已生成 AI 红娘深度建议。':'即时建议已生成；如需更深入分析，可单独请求一次。');
  const deep=$('#deep-analysis');deep.hidden=room.mode==='demo'||room.analysis_mode==='deep';deep.disabled=false;
  const names={true:'愿意真人继续',false:'暂不继续',null:'尚未决定'};
  $('#decision').textContent=isMember?`候选真人：${names[room.decisions.me]}；你：${names[room.decisions.owner]}。`:`你：${names[room.decisions.me]}；会员本人：${names[room.decisions.owner]}。`;
  $('#yes').textContent=isMember?'我愿意进入真人交流':'我愿意真人继续';
  const calibration=room.private_calibration||[];$('#calibration').hidden=!isMember||!calibration.length;$('#calibration-list').replaceChildren();calibration.forEach(item=>{const block=document.createElement('div');block.className='calibration-item';const title=document.createElement('strong');title.textContent=item.label;block.append(title);const note=document.createElement('p');note.className='subtle';note.textContent=item.high_impact?'这类信息会影响后续预会面的深度，可按你的意愿补充。':`本次交流中同类信息出现 ${item.count} 次，分身目前无法自然回答。`;const input=document.createElement('textarea');input.rows=2;input.maxLength=300;input.placeholder='可选：写下一句以后可由分身表达的想法';const allow=document.createElement('button');allow.textContent='补充并保存';allow.onclick=()=>calibrate(item.id,'allow',input.value);const dismiss=document.createElement('button');dismiss.className='secondary';dismiss.textContent='暂不处理';dismiss.onclick=()=>calibrate(item.id,'dismiss');block.append(note,input,allow,dismiss);$('#calibration-list').append(block);});
  $('#unlocked').hidden=!room.unlocked;
  const group=room.service_group;if(group){$('#handoff-link').href='handoff.html?room='+encodeURIComponent(id)+'&group='+encodeURIComponent(group.id)+'&actor='+encodeURIComponent(actor);}
}
async function act(action,extra={}){
  if(busy)return;busy=true;document.querySelectorAll('button').forEach(button=>button.disabled=true);
  try{const response=await fetch('/api/room',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,actor,action,...extra})});const data=await response.json();if(!response.ok)throw Error(data.error||'连接失败');room=data;if(!['ended','ready_for_handoff'].includes(room.status))throw Error('预会面尚未结束，请返回房间继续。');render();return true;}catch(err){error(err.message||String(err));return false;}finally{busy=false;document.querySelectorAll('button').forEach(button=>button.disabled=false);}
}
$('#deep-analysis').onclick=async()=>{const button=$('#deep-analysis');button.disabled=true;$('#analysis-status').textContent='AI 红娘正在生成更深入的建议，最长约 15 秒…';await act('analysis',{depth:'deep'});};
$('#yes').onclick=()=>act('decision',{agree:true});$('#no').onclick=()=>act('decision',{agree:false});
async function calibrate(item_id,choice,answer=''){try{const response=await fetch('/api/account',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'calibrate_topic',actor,room_id:id,item_id,choice,answer})});const data=await response.json();if(!response.ok)throw Error(data.error||'暂时无法保存校准');await act('state');}catch(err){error(err.message||String(err));}}
async function load(){if(await act('state')&&room.viewer_role==='candidate')await act('analysis');}
if(!id||!actor)error('缺少身份或房间标识，请从候选推荐开始。');else load();
