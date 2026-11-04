(() => {
  const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
  const actor=window.ZhiyuDemo?.actor||new URLSearchParams(location.search).get('actor');
  if(!actor){location.href='index.html';return}
  const storage='zhiyu-profile:'+actor;let state={};try{state=JSON.parse(localStorage.getItem(storage)||'{}')}catch(_){}
  const save=()=>localStorage.setItem(storage,JSON.stringify(state));
  const toast=t=>{const e=$('#toast');e.textContent=t;e.hidden=false;clearTimeout(window.toastTimer);window.toastTimer=setTimeout(()=>e.hidden=true,1900)};
  // 先保留一个可用的兜底项；完整的 31 省级行政区数据加载完成后才打开三级选择器，避免出现空白面板。
  let cities={江苏省:{南京市:['鼓楼区','建邺区','玄武区']}};
  const regionsReady=fetch('regions-data.js')
    .then(r=>r.ok?r.json():Promise.reject(new Error('地区数据加载失败')))
    .then(data=>{cities=data;return data})
    .catch(()=>cities);
  const occupationData={
    '人事/行政':['招聘专员','培训经理','培训专员','秘书','文员','后勤'],'财会/审计':['财务总监','财务经理','财务主管','会计','注册会计师','审计师','税务经理','税务专员','成本经理'],'销售':['销售总监','销售经理','销售主管','销售专员','渠道/分销经理','渠道/分销专员','经销商','客户经理','客户代表'],'律师/法务':['合伙人','律师','律师助理','法务经理','法务专员','知识产权专员'],'咨询/顾问':['专业顾问','咨询经理','咨询师','培训师'],'高级管理':['总经理','副总经理','合伙人','总监','经理','总裁助理'],'IT/互联网':['管理者/负责人','产品经理','设计师','工程师','测试','运营师','分析师','项目管理'],'政府机构':['公务员','事业编制','警察'],'医疗/护理':['医生','药剂师','护士','医疗管理','兽医'],'教育/科研':['教授/副教授','讲师/助教','职业技术教师','中学教师','小学教师','幼师','教务管理人员','科研人员','科研管理人员','培训师'],'金融/银行/保险':['投资','保险','金融','银行','证券'],'建筑/房地产':['建筑师','工程师','规划师','景观设计','房地产策划','房地产交易','物业管理'],'通信/电子':['通信技术','电子技术'],'传媒/艺术':['主编','编辑','作家','撰稿人','设计师','文案策划','出版发行','记者','导演','演员','音乐家','舞蹈','主持人','经纪人','模特','摄影师','影视后期制作'],'广告/市场':['广告客户经理','广告客户专员','广告设计经理','广告设计专员','广告策划','市场营销经理','市场营销专员','市场策划','市场调研与分析','市场拓展','公关经理','公关专员','媒介经理','媒介专员','品牌经理','品牌专员'],'生产/制造':['工厂经理','工程师','项目主管','营运经理','营运主管','车间主任','物料管理','生产领班','操作工人','安全管理'],'服务业':['客户服务','餐饮管理','厨师','餐厅服务员','酒店管理','大堂经理','酒店服务员','导游','美容师','健身教练','商场经理','零售店店长','店员','保安经理','保安人员','家政服务'],'交通运输':['飞行员','空乘人员','地勤人员','列车司机','乘务员','船长','船员','司机'],'商贸/采购':['商务经理','商务专员','采购经理','采购专员','外贸经理','外贸专员','业务跟单','报关员'],'生物/制药':['生物工程','药品生产','临床研究','医疗器械','医药代表','化工工程师'],'物流/仓储':['物流经理','物流主管','物流专员','仓库经理','仓库管理员','货运代理','集装箱业务','海关事务管理','报单员','快递员'],'农林牧渔':['农业','林业','畜牧业','渔业'],'自由职业':['学生'],'其他职业':['待业']};
  const preferenceOccupationOptions=[...Object.keys(occupationData),'学生','待业'];
  const lists={income:['10万以下','10–20万','20–30万','30–60万','60–100万','100万以上'],familyAssets:['100万以内','100–500万','500–1000万','1000–2000万','2000–5000万','5000万以上','不确定'],mbti:['INTJ','INTP','ENTJ','ENTP','INFJ','INFP','ENFJ','ENFP','ISTJ','ISFJ','ESTJ','ESFJ','ISTP','ISFP','ESTP','ESFP']};
  const titles={birthday:'选择生日',height:'选择身高',city:'选择现居地',hometown:'选择家乡',preferredCity:'选择倾向现居地',income:'选择年收入',prefIncome:'选择最低年收入',occupation:'选择职业',prefOccupation:'对方的职业',familyAssets:'家庭资产',prefFamilyAssets:'家庭资产',mbti:'MBTI',ageRange:'选择年龄范围',heightRange:'选择身高范围'};
  const setValue=(key,val)=>{const e=$('#value-'+key),text=Array.isArray(val)?val.join('、'):val;if(e)e.innerHTML=(text||'请选择')+' <i>›</i>'};
  const preferenceOccupationTrigger=$('[data-picker="prefOccupation"]');
  if(preferenceOccupationTrigger){preferenceOccupationTrigger.querySelector('b').textContent='对方职业';const hint=document.createElement('small');hint.textContent='可多选';preferenceOccupationTrigger.querySelector('span').append(hint)}
  const update=()=>{
    $$('[data-field]').forEach(g=>{const v=state[g.dataset.field],multi=g.dataset.multiple==='true';g.querySelectorAll('button').forEach(b=>b.classList.toggle('selected',multi?Array.isArray(v)&&v.includes(b.dataset.value):v===b.dataset.value))});
    $$('[data-tags]').forEach(g=>g.querySelectorAll('button').forEach(b=>b.classList.toggle('selected',(state[g.dataset.tags]||[]).includes(b.textContent))));
    Object.keys(titles).forEach(k=>setValue(k,state[k]));
    const n=['gender','birthday','height','education','city','marital'].filter(k=>state[k]).length,p=Math.round(n/6*100);$('#completion-text').textContent=p+'%';$('#completion-bar').style.width=p+'%';
    const note=$('#preference-note');if(note&&note.value!==(state.preferenceNote||''))note.value=state.preferenceNote||'';
    $$('#priority-grid button').forEach(b=>b.classList.toggle('selected',(state.priorities||[]).includes(b.dataset.priority)));
  };
  const mask=$('#picker-mask'),body=$('#picker-body'),picker={key:'',value:{}};
  const setPickerConfirm=enabled=>{const button=$('#picker-confirm');button.disabled=!enabled;button.setAttribute('aria-disabled',String(!enabled))};
  const wheel=(values,selected,pick)=>{const d=document.createElement('div');d.className='wheel';values.forEach(v=>{const b=document.createElement('button');b.type='button';b.textContent=v;b.classList.toggle('selected',String(v)===String(selected));b.onclick=()=>{d.querySelectorAll('button').forEach(x=>x.classList.remove('selected'));b.classList.add('selected');pick(String(v))};d.append(b)});setTimeout(()=>d.querySelector('.selected')?.scrollIntoView({block:'center'}),0);return d};
  const grid=(values,selected,pick)=>{const d=document.createElement('div');d.className='picker-grid';values.forEach(v=>{const b=document.createElement('button');b.type='button';b.textContent=v;b.classList.toggle('selected',v===selected);b.onclick=()=>{d.querySelectorAll('button').forEach(x=>x.classList.remove('selected'));b.classList.add('selected');picker.value.value=v;pick(v)};d.append(b)});return d};
  const makeCity=key=>{
    const old=(state[key]||'').split('·'),provinces=Object.keys(cities);
    // 新建资料时不预选任何项：必须依次明确选择省、市、区县。
    picker.value={province:old.length===3?old[0]:'',city:old.length===3?old[1]:'',district:old.length===3?old[2]:''};
    const labels=document.createElement('div');labels.className='location-tabs';
    const cols=document.createElement('div');cols.className='picker-columns three';
    const emptyWheel=text=>{const item=document.createElement('div');item.className='wheel is-disabled';item.innerHTML='<span>'+text+'</span>';return item};
    const render=()=>{
      const names=picker.value.province&&cities[picker.value.province]?Object.keys(cities[picker.value.province]):[];
      if(picker.value.city&&!names.includes(picker.value.city)){picker.value.city='';picker.value.district=''};
      const areas=picker.value.city?(cities[picker.value.province][picker.value.city]||[]):[];
      if(picker.value.district&&!areas.includes(picker.value.district))picker.value.district='';
      const active=picker.value.province?(picker.value.city?2:1):0;
      labels.replaceChildren(...[
        ['请选择省份',picker.value.province],['请选择城市',picker.value.city],['请选择区县',picker.value.district]
      ].map(([fallback,value],index)=>{const item=document.createElement('span');item.textContent=value||fallback;item.classList.toggle('active',index===active);return item}));
      cols.replaceChildren(
        wheel(provinces,picker.value.province,v=>{picker.value.province=v;picker.value.city='';picker.value.district='';render()}),
        names.length?wheel(names,picker.value.city,v=>{picker.value.city=v;picker.value.district='';render()}):emptyWheel('先选省份'),
        areas.length?wheel(areas,picker.value.district,v=>{picker.value.district=v;render()}):emptyWheel(picker.value.province?'先选城市':'等待选择')
      );
      setPickerConfirm(Boolean(picker.value.province&&picker.value.city&&picker.value.district));
    };
    render();body.append(labels,cols)
  };
  const makeRange=(key,lo,hi,suffix)=>{const got=(state[key]||'').match(/(\d+).+?(\d+)/)||[];picker.value={min:got[1]||String(lo),max:got[2]||String(hi)};const values=Array.from({length:hi-lo+1},(_,i)=>String(lo+i)+suffix),cols=document.createElement('div');cols.className='picker-columns two';cols.append(wheel(values,picker.value.min+suffix,v=>picker.value.min=v.replace(suffix,'')),wheel(values,picker.value.max+suffix,v=>picker.value.max=v.replace(suffix,'')));body.append(cols)};
  const showPicker=key=>{
    // 三级地区数据异步加载。用户若比数据加载更早点击，展示加载状态，完成后自动进入选择器。
    if(['city','hometown','preferredCity'].includes(key)&&Object.keys(cities).length<31){
      picker.key=key;body.replaceChildren();$('#picker-title').textContent='正在加载地区数据';setPickerConfirm(false);
      const loading=document.createElement('p');loading.className='picker-loading';loading.textContent='正在准备全国省、市、区县数据…';body.append(loading);mask.hidden=false;
      regionsReady.then(()=>showPicker(key));
      return;
    }
    picker.key=key;picker.value={};body.replaceChildren();$('#picker-title').textContent=titles[key]||'请选择';setPickerConfirm(true);
    if(['city','hometown','preferredCity'].includes(key))makeCity(key);
    else if(key==='birthday'){const m=(state.birthday||'').match(/(\d+)年(\d+)月(\d+)/)||[];picker.value={year:m[1]||'1995',month:m[2]||'1',day:m[3]||'1'};const cols=document.createElement('div');cols.className='picker-columns three';const render=()=>{const days=Array.from({length:new Date(+picker.value.year,+picker.value.month,0).getDate()},(_,i)=>String(i+1));cols.replaceChildren(wheel(Array.from({length:47},(_,i)=>String(2006-i)),picker.value.year,v=>{picker.value.year=v;render()}),wheel(Array.from({length:12},(_,i)=>String(i+1)),picker.value.month,v=>{picker.value.month=v;render()}),wheel(days,picker.value.day,v=>picker.value.day=v))};render();body.append(cols)}
    else if(key==='height'){const h=(state.height||'168cm').replace('cm','');picker.value={value:h};const cols=document.createElement('div');cols.className='picker-columns one';cols.append(wheel(Array.from({length:101},(_,i)=>String(140+i)+'cm'),h+'cm',v=>picker.value.value=v.replace('cm','')));body.append(cols)}
    else if(key==='ageRange')makeRange(key,20,55,'岁');else if(key==='heightRange')makeRange(key,145,210,'cm');
    else if(key==='occupation'){const old=(state[key]||'').split(' / '),cols=document.createElement('div');cols.className='picker-columns two';picker.value={industry:old[0]||Object.keys(occupationData)[0],role:old[1]||''};const render=()=>{if(!occupationData[picker.value.industry])picker.value.industry=Object.keys(occupationData)[0];const roles=occupationData[picker.value.industry];if(!roles.includes(picker.value.role))picker.value.role=roles[0];cols.replaceChildren(wheel(Object.keys(occupationData),picker.value.industry,v=>{picker.value.industry=v;render()}),wheel(roles,picker.value.role,v=>picker.value.role=v))};render();body.append(cols)}
    else if(key==='prefOccupation'){const previous=Array.isArray(state[key])?state[key]:(state[key]?[String(state[key]).split(' / ')[0]]:[]);picker.value={values:previous.filter(v=>preferenceOccupationOptions.includes(v))};const choices=document.createElement('div');choices.className='picker-grid occupation-preference-grid';const render=()=>{choices.replaceChildren(...preferenceOccupationOptions.map(v=>{const button=document.createElement('button');button.type='button';button.textContent=v;button.classList.toggle('selected',picker.value.values.includes(v));button.onclick=()=>{picker.value.values=picker.value.values.includes(v)?picker.value.values.filter(x=>x!==v):picker.value.values.concat(v);render()};return button}));setPickerConfirm(picker.value.values.length>0)};render();body.append(choices)}
    else {const source=key.startsWith('pref')?key.slice(4,5).toLowerCase()+key.slice(5):key;picker.value={value:state[key]||''};body.append(grid(lists[source]||lists[key]||[],picker.value.value,v=>picker.value.value=v))}
    mask.hidden=false};
  const close=()=>{mask.hidden=true;body.replaceChildren();setPickerConfirm(true)};
  $$('.picker-trigger').forEach(b=>b.onclick=()=>showPicker(b.dataset.picker));$('#picker-cancel').onclick=close;mask.onclick=e=>{if(e.target===mask)close()};
  $('#picker-confirm').onclick=()=>{const k=picker.key,v=picker.value;if(['city','hometown','preferredCity'].includes(k)&&!(v.province&&v.city&&v.district)){toast('请依次选择省、市、区县');return}if(k==='prefOccupation'&&!v.values.length){toast('请至少选择一个职业类别');return}if(k==='birthday')state[k]=v.year+'年'+v.month+'月'+v.day+'日';else if(k==='height')state[k]=v.value+'cm';else if(['city','hometown','preferredCity'].includes(k))state[k]=v.province+'·'+v.city+'·'+v.district;else if(k==='ageRange')state[k]=v.min+'–'+v.max+'岁';else if(k==='heightRange')state[k]=v.min+'–'+v.max+'cm';else if(k==='occupation')state[k]=v.industry+' / '+v.role;else if(k==='prefOccupation')state[k]=v.values;else state[k]=v.value;save();update();close()};
  $$('[data-field]').forEach(g=>g.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;const k=g.dataset.field;if(g.dataset.multiple==='true'){const old=state[k]||[];state[k]=old.includes(b.dataset.value)?old.filter(x=>x!==b.dataset.value):old.concat(b.dataset.value)}else state[k]=b.dataset.value;save();update()}));
  $$('[data-tags]').forEach(g=>g.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;const k=g.dataset.tags,old=state[k]||[];state[k]=old.includes(b.textContent)?old.filter(x=>x!==b.textContent):old.concat(b.textContent);save();update()}));
  $('#priority-grid').onclick=e=>{const b=e.target.closest('button');if(!b)return;const old=state.priorities||[];if(old.includes(b.dataset.priority))state.priorities=old.filter(x=>x!==b.dataset.priority);else if(old.length>=4)toast('最多优先选择 4 项');else state.priorities=old.concat(b.dataset.priority);save();update()};
  $('#preference-note').oninput=e=>{state.preferenceNote=e.target.value;save()};
  $$('.profile-tabs button').forEach(b=>b.onclick=()=>{const id=b.dataset.tab;$$('.profile-tabs button').forEach(x=>x.classList.toggle('active',x===b));$$('.profile-panel').forEach(x=>{x.hidden=x.id!==id;x.classList.toggle('active',x.id===id)});window.scrollTo({top:0,behavior:'smooth'})});
  const tab=x=>$('.profile-tabs button[data-tab="'+x+'"]').click();
  const api=async data=>{const r=await fetch('/api/account',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}),d=await r.json();if(!r.ok)throw Error(d.error||'保存失败');return d};
  const photoGrid=$('#photo-grid'),photoInput=$('#photo-input'),photoNote=$('#photo-note');
  const renderPhotos=(photos=[])=>{
    if(!photoGrid)return;
    photoGrid.replaceChildren();
    const add=document.createElement('button');add.type='button';add.className='photo-add';add.innerHTML='<b>＋</b><span>'+(!photos.length?'上传封面照':'添加照片')+'</span>';
    add.disabled=photos.length>=6;add.onclick=()=>photoInput.click();photoGrid.append(add);
    photos.forEach((photo,index)=>{const item=document.createElement('figure');item.className='photo-item';const image=document.createElement('img');image.src=photo.url;image.alt='我的照片 '+(index+1);const remove=document.createElement('button');remove.type='button';remove.textContent='×';remove.setAttribute('aria-label','删除照片');remove.onclick=async()=>{try{await api({action:'delete_photo',actor,photo_id:photo.id});await loadPhotos();toast('照片已删除')}catch(e){toast(e.message||'删除失败')}};item.append(image,remove);photoGrid.append(item)});
    photoNote.textContent=photos.length?`已上传 ${photos.length} / 6 张。支持 JPG、PNG、WebP，单张不超过 3MB。`:'支持 JPG、PNG、WebP，单张不超过 3MB。';
  };
  const loadPhotos=async()=>{try{const data=await api({action:'photos',actor});renderPhotos(data.photos||[])}catch(_){renderPhotos([])}};
  if(photoInput){photoInput.onchange=async()=>{const file=photoInput.files&&photoInput.files[0];photoInput.value='';if(!file)return;if(file.size>3*1024*1024){toast('单张图片请控制在 3MB 以内');return}try{const dataUrl=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(file)});photoNote.textContent='正在上传照片…';await api({action:'upload_photo',actor,data_url:dataUrl});await loadPhotos();toast('照片已保存')}catch(e){toast(e.message||'上传失败')}}};
  const hydrateFromAccount=async()=>{
    try{
      const [me,snapshot]=await Promise.all([api({action:'me',actor}),api({action:'onboarding',actor})]);
      const pub=me.public||{},priv=me.private||{},onboarding=snapshot.data||{};
      const stored={
        ...onboarding,
        gender:pub.gender, birthday:priv.birthday, height:pub.height, education:pub.education,
        city:priv.city||pub.city, housing:pub.housing||priv.housing, vehicle:pub.vehicle||priv.vehicle,
        marital:pub.marital, income:priv.income, occupation:priv.occupation||pub.occupation,
        onlyChild:priv.onlyChild, familyAssets:priv.familyAssets, hometown:priv.hometown,
        loveCount:priv.loveCount, childrenPlan:priv.childrenPlan,
        relationshipGoal:pub.relationship_goal, tags:Array.isArray(pub.interests)?pub.interests:undefined,
        mbti:priv.mbti || (String(pub.communication||'').replace(/^MBTI[：:]/,'')),
      };
      Object.keys(stored).forEach(key=>{if(stored[key]!==undefined && stored[key]!==null && stored[key]!=='') state[key]=stored[key]});
      save(); update(); await loadPhotos();
    }catch(_){
      // Offline/local fallback: retain the browser draft and let normal save retry later.
    }
  };
  const persist=async()=>{const me=await api({action:'me',actor}),pub=Object.assign({},me.public,{nickname:me.account.nickname,relationship_goal:state.relationshipGoal||me.public.relationship_goal||'',interests:state.tags||me.public.interests||[],communication:state.mbti?'MBTI：'+state.mbti:(me.public.communication||'')});await api({action:'save_public',actor,version:me.version,public:pub});await api({action:'save_onboarding',actor,data:state});save()};
  $('#submit-basic').onclick=async()=>{const bad=['gender','birthday','height','education','city','marital'].filter(k=>!state[k]);if(bad.length){toast('请先完成所有必填基础资料');return}try{await persist();toast('基础资料已保存');setTimeout(()=>tab('life'),400)}catch(e){toast(e.message||'保存失败')}};
  $('#submit-life').onclick=async()=>{try{await persist();toast('补充资料已保存');setTimeout(()=>tab('preference'),400)}catch(e){toast(e.message||'保存失败')}};
  $('#submit-preference').onclick=async()=>{try{await persist();toast('偏好已保存，正在进入推荐');setTimeout(()=>location.href='matches.html?actor='+encodeURIComponent(actor),500)}catch(e){toast(e.message||'保存失败')}};
  $('#save-top').onclick=()=>{save();toast('已暂存到本机浏览器')};$('#back').onclick=()=>history.length>1?history.back():location.href='index.html';update();hydrateFromAccount();loadPhotos();
})();
