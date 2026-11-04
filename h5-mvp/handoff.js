const $=s=>document.querySelector(s);
const params=new URLSearchParams(location.search),groupId=params.get('group'),actor=params.get('actor')||ZhiyuDemo.actor,roomId=params.get('room');
let group=null,busy=false;
function error(message){$('#error').hidden=false;$('#error').textContent=message;}
function render(){
  const active=group.status==='active';
  $('#status').textContent=active?'服务群等待微信接入':'7 天服务期已结束';
  $('#title').textContent=active?'7 天真人接管服务':'本次真人接管服务已结束';
  const seconds=Math.max(0,Math.ceil(group.deadline-Date.now()/1000));$('#clock').textContent=active?`剩余 ${Math.floor(seconds/86400)} 天 ${Math.floor(seconds%86400/3600)} 小时。本地记录已建立，等待正式微信服务群能力接入。`:'服务期结束后，不再提供群内 AI 服务。';
  $('#scope').replaceChildren();group.service_scope.forEach(item=>{const li=document.createElement('li');li.textContent=item;$('#scope').append(li);});
  $('#support').textContent=group.human_support_requested?'已申请人工红娘协助':'申请人工红娘协助';
  $('#support-state').textContent=group.human_support_requested?'本地工单已记录；正式上线后由人工红娘系统处理。':'';
  $('#report-state').textContent=group.my_safety_reports.length?`已记录 ${group.my_safety_reports.length} 条仅自己可见的安全协助请求。`:'';
  ['suggest','support','report','report-detail'].forEach(id=>$('#'+id).disabled=!active);
  $('#back').href=actor==='demo_member'?ZhiyuDemo.query('member.html',{actor}):ZhiyuDemo.query('matches.html',{actor});
}
async function act(action,extra={}){
  if(busy)return;busy=true;document.querySelectorAll('button').forEach(button=>button.disabled=true);
  try{const response=await fetch('/api/group',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:groupId,actor,action,...extra})});const data=await response.json();if(!response.ok)throw Error(data.error||'服务暂时不可用');group=data;render();return data;}catch(err){error(err.message||String(err));}finally{busy=false;document.querySelectorAll('button').forEach(button=>button.disabled=false);}
}
$('#suggest').onclick=async()=>{const result=await act('date_suggestion');if(result)$('#suggestion').textContent=result.date_suggestion||'';};
$('#support').onclick=()=>act('request_human_support');
$('#report').onclick=async()=>{const detail=$('#report-detail').value.trim();if(!detail)return error('请先填写情况说明。');if(await act('safety_report',{detail}))$('#report-detail').value='';};
if(!groupId||!actor||!roomId)error('缺少服务群或身份标识，请从预会面结果页进入。');else act('state');
