const $=s=>document.querySelector(s), actor=ZhiyuDemo.actor;
let snapshot=null, option=null, busy=false;
const draftKey='zhiyu-light-draft-'+actor;
$('#interview-entry').href=ZhiyuDemo.query('interview.html');
for(const [id,path] of [['back','twin.html'],['rooms','member.html'],['finish','member.html'],['legacy','twin.html']])$('#'+id).href=ZhiyuDemo.query(path);
async function api(action,extra={}){const r=await fetch('/api/account',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,actor,...extra})});const d=await r.json();if(!r.ok)throw Error(d.error||'暂时无法保存，请重试');return d;}
function fail(e){$('#error').hidden=false;$('#error').textContent=e.message;}
function render(){const {state:s,question:q,consent,facts}=snapshot;option=null;
  $('#progress').textContent=`已记录 ${s.answers.length} 条回答 · ${q?q.topic:'本轮主题已浏览完'} · 可随时结束`;
  $('#question').textContent=s.status==='paused'?'已暂停，下次从这里继续':s.status==='complete'?'这一轮先到这里，随时回来补充':s.phase==='followup'?s.followup:q.prompt;
  const active=s.status==='active';$('#choices').replaceChildren();
  if(active&&s.phase==='main')q.options.forEach((value,i)=>{const b=document.createElement('button');b.type='button';b.textContent=value;b.onclick=()=>{option=i;$('#answer').value='';localStorage.removeItem(draftKey);$('#choices').querySelectorAll('button').forEach(x=>x.classList.toggle('selected',x===b));};$('#choices').append(b);});
  for(const id of ['submit','next','change','skip','pause','answer'])$('#'+id).hidden=!active;
  $('#resume').hidden=s.status!=='paused';$('#notice').textContent=s.notice||'回答随时可保存，不需要答完全部问题。';
  $('#answer').value=s.draft||'';
  if(consent.choice!==null)$(`input[name="consent"][value="${consent.choice?'yes':'no'}"]`).checked=true;
  $('#consent-note').textContent=consent.choice===null?'尚未选择，不会自动视为同意。':consent.choice?'当前允许使用普通偏好。':'当前暂不允许使用普通偏好。';
  const box=$('#facts');box.replaceChildren();facts.filter(f=>!f.deleted).forEach(f=>{const line=document.createElement('div');line.className='light-fact';const p=document.createElement('p');p.textContent=f.text;const meta=document.createElement('small');meta.textContent=`${f.topic} · ${f.outward?'本人提供的普通偏好，仍受使用范围控制':'本人输入，仅自己可见'} · ${f.question_version}`;const del=document.createElement('button');del.type='button';del.textContent='删除这条';del.onclick=async()=>{try{snapshot=await api('light_delete_fact',{fact_id:f.id});render();}catch(e){fail(e);}};const edit=document.createElement('button');edit.type='button';edit.textContent='重新回答';edit.onclick=()=>run('revisit',{question_id:f.question_id});line.append(p,meta,edit,del);box.append(line);});
  for(const note of snapshot.legacy_notes||[]){const line=document.createElement('div');line.className='light-fact';const title=document.createElement('b');title.textContent=note.question;const value=document.createElement('p');value.textContent=note.text;const scope=document.createElement('small');scope.textContent='原会后校准 · 保留为私密记录，未自动开放';line.append(title,value,scope);box.append(line);}
}
async function run(operation,extra={}){if(busy||!snapshot)return;busy=true;$('#error').hidden=true;document.querySelectorAll('button').forEach(b=>b.disabled=true);const text=$('#answer').value;try{snapshot=await api('light_act',{operation,revision:snapshot.state.revision,text,option:operation==='answer'?option:null,...extra});localStorage.removeItem(draftKey);render();}catch(e){fail(e);localStorage.setItem(draftKey,JSON.stringify({revision:snapshot.state.revision,text}));}finally{busy=false;document.querySelectorAll('button').forEach(b=>b.disabled=false);}}
$('#answer').oninput=()=>{option=null;$('#choices').querySelectorAll('button').forEach(b=>b.classList.remove('selected'));if(snapshot)localStorage.setItem(draftKey,JSON.stringify({revision:snapshot.state.revision,text:$('#answer').value}));};
for(const [id,op] of [['submit','answer'],['next','next'],['change','change'],['skip','skip_topic'],['pause','pause'],['resume','resume']])$('#'+id).onclick=()=>run(op);
$('#save-consent').onclick=async()=>{const picked=$('input[name="consent"]:checked');if(!picked)return fail(Error('请先选择允许或暂不允许'));try{snapshot=await api('expression_consent',{allowed:picked.value==='yes'});const draft=$('#answer').value;render();$('#answer').value=draft;$('#consent-note').textContent='使用范围已保存，进行中房间的下一条回复会使用新范围。';}catch(e){fail(e);}};
$('#finish').onclick=async e=>{if(!snapshot||snapshot.state.status!=='active')return;e.preventDefault();await run('pause');if(snapshot.state.status==='paused')location.href=$('#finish').href;};
(async()=>{try{snapshot=await api('light_me');render();const draft=JSON.parse(localStorage.getItem(draftKey)||'null');if(draft&&draft.revision===snapshot.state.revision)$('#answer').value=draft.text;}catch(e){fail(e);}})();
