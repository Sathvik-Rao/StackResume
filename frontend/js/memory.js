// ── Memory ──────────────────────────────────────────────────────────────────
async function loadMemoryChip(){}

// Month helpers
const _MO=['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
function _monthSel(val,cls){
  let o=`<option value="">Mo.</option>`;
  for(let i=1;i<=12;i++)o+=`<option value="${i}"${val==i?' selected':''}>${_MO[i]}</option>`;
  return`<select class="fs ${cls}" style="width:72px">${o}</select>`;
}
function _typeOpts(val){
  const types=['Full-time','Part-time','Contract','Freelance','Internship'];
  return`<option value="">Type</option>`+types.map(t=>`<option${val===t?' selected':''}>${t}</option>`).join('');
}
function _profOpts(val){
  const p=['Native','Fluent','Professional','Conversational','Basic'];
  return p.map(x=>`<option${val===x?' selected':''}>${x}</option>`).join('');
}

function addCompanyRow(d={}){
  const c=document.getElementById('m-companies-rows');
  const el=document.createElement('div');
  el.className='mem-entry';
  const present=!d.to_year&&!d.to_month;
  el.innerHTML=`
    <div class="mem-entry-header">
      <span class="mem-entry-num">Work Experience</span>
      <button class="mem-entry-del" onclick="this.closest('.mem-entry').remove()">×</button>
    </div>
    <div class="frow">
      <div class="fg"><label class="fl">Company</label><input type="text" class="fi m-co-name" value="${esc(d.name||'')}" placeholder="Google"></div>
      <div class="fg"><label class="fl">Title / Position</label><input type="text" class="fi m-co-title" value="${esc(d.title||'')}" placeholder="Senior Software Engineer"></div>
    </div>
    <div class="frow">
      <div class="fg"><label class="fl">Location</label><input type="text" class="fi m-co-loc" value="${esc(d.location||'')}" placeholder="Mountain View, CA / Remote"></div>
      <div class="fg"><label class="fl">Employment Type</label><select class="fs m-co-type">${_typeOpts(d.employment_type)}</select></div>
    </div>
    <div class="mem-date-row">
      <div class="fg"><label class="fl">From</label>
        <div style="display:flex;gap:6px">${_monthSel(d.from_month,'m-co-fm')}
          <input type="number" class="fi m-co-fy" placeholder="Year" value="${d.from_year||''}" min="1950" max="2035" style="flex:1"></div>
      </div>
      <div class="fg"><label class="fl">To</label>
        <div style="display:flex;gap:6px;align-items:center">
          ${_monthSel(present?'':d.to_month,'m-co-tm')}
          <input type="number" class="fi m-co-ty" placeholder="Year" value="${present?'':d.to_year||''}" min="1950" max="2035" style="flex:1" ${present?'disabled':''}>
          <label class="mem-present-label"><input type="checkbox" class="m-co-present" ${present?'checked':''} onchange="_togglePresent(this)"> Present</label>
        </div>
      </div>
    </div>
    <div class="fg" style="margin-top:6px"><label class="fl">Description <span style="color:var(--text3)">(optional — key achievements, responsibilities, tech used)</span></label>
      <textarea class="fta m-co-desc" placeholder="• Led migration from monolith to microservices, reducing deploy time by 60%&#10;• Built real-time analytics pipeline handling 50k events/sec" style="min-height:64px;font-size:13px">${esc(d.description||'')}</textarea>
    </div>`;
  c.appendChild(el);
}
function _togglePresent(cb){
  const row=cb.closest('.mem-entry');
  const ty=row.querySelector('.m-co-ty'),tm=row.querySelector('.m-co-tm');
  ty.disabled=tm.disabled=cb.checked;
  if(cb.checked){ty.value='';tm.value='';}
}

function addEduRow(d={}){
  const c=document.getElementById('m-edu-rows');
  const el=document.createElement('div');
  el.className='mem-entry';
  el.innerHTML=`
    <div class="mem-entry-header">
      <span class="mem-entry-num">Education</span>
      <button class="mem-entry-del" onclick="this.closest('.mem-entry').remove()">×</button>
    </div>
    <div class="frow">
      <div class="fg"><label class="fl">Institution</label><input type="text" class="fi m-edu-inst" value="${esc(d.institution||'')}" placeholder="MIT"></div>
      <div class="fg"><label class="fl">Degree</label><input type="text" class="fi m-edu-deg" value="${esc(d.degree||'')}" placeholder="B.S., M.S., Ph.D…"></div>
    </div>
    <div class="frow">
      <div class="fg"><label class="fl">Field of Study</label><input type="text" class="fi m-edu-fos" value="${esc(d.field_of_study||'')}" placeholder="Computer Science"></div>
      <div class="fg"><label class="fl">Graduation Year</label><input type="number" class="fi m-edu-gy" value="${d.graduation_year||''}" placeholder="2019" min="1950" max="2035"></div>
    </div>
    <div class="frow">
      <div class="fg"><label class="fl">GPA <span style="color:var(--text3)">(optional)</span></label><input type="text" class="fi m-edu-gpa" value="${esc(d.gpa||'')}" placeholder="3.9 / 4.0"></div>
      <div class="fg"><label class="fl">Honors <span style="color:var(--text3)">(optional)</span></label><input type="text" class="fi m-edu-hon" value="${esc(d.honors||'')}" placeholder="Summa Cum Laude…"></div>
    </div>`;
  c.appendChild(el);
}

function addCertRow(d={}){
  const c=document.getElementById('m-cert-rows');
  const el=document.createElement('div');
  el.className='mem-entry';
  el.innerHTML=`
    <div class="mem-entry-header">
      <span class="mem-entry-num">Certification</span>
      <button class="mem-entry-del" onclick="this.closest('.mem-entry').remove()">×</button>
    </div>
    <div class="frow">
      <div class="fg"><label class="fl">Name</label><input type="text" class="fi m-cert-name" value="${esc(d.name||'')}" placeholder="AWS Solutions Architect"></div>
      <div class="fg"><label class="fl">Issuer</label><input type="text" class="fi m-cert-issuer" value="${esc(d.issuer||'')}" placeholder="Amazon Web Services"></div>
    </div>
    <div class="frow">
      <div class="fg"><label class="fl">Year</label><input type="number" class="fi m-cert-year" value="${d.year||''}" placeholder="2023" min="2000" max="2035"></div>
      <div class="fg"><label class="fl">URL <span style="color:var(--text3)">(optional)</span></label><input type="text" class="fi m-cert-url" value="${esc(d.url||'')}" placeholder="credly.com/badges/…"></div>
    </div>`;
  c.appendChild(el);
}

function addProjectRow(d={}){
  const c=document.getElementById('m-projects-rows');
  const el=document.createElement('div');
  el.className='mem-entry';
  el.innerHTML=`
    <div class="mem-entry-header">
      <span class="mem-entry-num">Project</span>
      <button class="mem-entry-del" onclick="this.closest('.mem-entry').remove()">×</button>
    </div>
    <div class="frow">
      <div class="fg"><label class="fl">Project Name</label><input type="text" class="fi m-proj-name" value="${esc(d.name||'')}" placeholder="StackResume, OpenMetrics…"></div>
      <div class="fg"><label class="fl">Your Role <span style="color:var(--text3)">(optional)</span></label><input type="text" class="fi m-proj-role" value="${esc(d.role||'')}" placeholder="Lead Developer, Contributor…"></div>
    </div>
    <div class="frow">
      <div class="fg"><label class="fl">URL <span style="color:var(--text3)">(optional)</span></label><input type="text" class="fi m-proj-url" value="${esc(d.url||'')}" placeholder="github.com/you/project"></div>
      <div class="fg"><label class="fl">Year <span style="color:var(--text3)">(optional)</span></label><input type="number" class="fi m-proj-year" value="${d.year||''}" placeholder="2024" min="1990" max="2035"></div>
    </div>
    <div class="fg"><label class="fl">Technologies <span style="color:var(--text3)">(comma-separated)</span></label><input type="text" class="fi m-proj-tech" value="${esc((d.technologies||[]).join(', '))}" placeholder="React, Node.js, PostgreSQL…"></div>
    <div class="fg"><label class="fl">Description</label><textarea class="fta m-proj-desc" placeholder="What it does and what you built / contributed…" style="min-height:60px;font-size:13px">${esc(d.description||'')}</textarea></div>`;
  c.appendChild(el);
}

function addLangRow(d={}){
  const c=document.getElementById('m-lang-rows');
  const el=document.createElement('div');
  el.className='mem-entry';
  el.style.padding='10px 14px';
  el.innerHTML=`
    <div style="display:flex;gap:8px;align-items:center">
      <input type="text" class="fi m-lang-lang" value="${esc(d.language||'')}" placeholder="English, Spanish, Mandarin…" style="flex:2">
      <select class="fs m-lang-prof" style="flex:1">${_profOpts(d.proficiency||'Fluent')}</select>
      <button class="mem-entry-del" onclick="this.closest('.mem-entry').remove()">×</button>
    </div>`;
  c.appendChild(el);
}

async function openMemory(){
  try{
    const r=await fetch(`${API}/api/memory`);
    const m=await r.json();
    document.getElementById('m-name').value=m.full_name||'';
    document.getElementById('m-email').value=m.email||'';
    document.getElementById('m-phone').value=m.phone||'';
    document.getElementById('m-loc').value=m.location||'';
    document.getElementById('m-summary').value=m.summary||'';
    document.getElementById('m-li').value=m.linkedin_url||'';
    document.getElementById('m-gh').value=m.github_url||'';
    document.getElementById('m-web').value=m.website||'';
    document.getElementById('m-portfolio').value=m.portfolio_url||'';
    document.getElementById('m-yrs').value=m.total_years_experience||'';
    document.getElementById('m-workauth').value=m.work_authorization||'';
    document.getElementById('m-roles').value=(m.target_roles||[]).join(', ');
    document.getElementById('m-skills').value=(m.always_include_skills||[]).join(', ');
    document.getElementById('m-availability').value=m.availability||'';
    document.getElementById('m-remote').checked=!!m.open_to_remote;
    document.getElementById('m-notes').value=m.personal_notes||'';
    // Dynamic rows
    document.getElementById('m-companies-rows').innerHTML='';
    document.getElementById('m-projects-rows').innerHTML='';
    document.getElementById('m-edu-rows').innerHTML='';
    document.getElementById('m-cert-rows').innerHTML='';
    document.getElementById('m-lang-rows').innerHTML='';
    (m.companies||[]).forEach(c=>addCompanyRow(c));
    (m.projects||[]).forEach(p=>addProjectRow(p));
    (m.education||[]).forEach(e=>addEduRow(e));
    (m.certifications||[]).forEach(c=>addCertRow(c));
    (m.languages_spoken||[]).forEach(l=>addLangRow(l));
  }catch(e){}
  // Reset to first tab
  const modal=document.getElementById('mem-modal');
  modal.querySelectorAll('.set-tab').forEach((t,i)=>t.classList.toggle('on',i===0));
  modal.querySelectorAll('.set-pane').forEach((p,i)=>p.classList.toggle('on',i===0));
  modal.classList.add('open');
}

function closeMem(){document.getElementById('mem-modal').classList.remove('open')}

async function saveMem(){
  const parseList=s=>s.split(',').map(x=>x.trim()).filter(Boolean);
  const companies=[...document.querySelectorAll('#m-companies-rows .mem-entry')].map(row=>{
    const present=row.querySelector('.m-co-present').checked;
    return{
      name:row.querySelector('.m-co-name').value.trim()||null,
      title:row.querySelector('.m-co-title').value.trim()||null,
      location:row.querySelector('.m-co-loc').value.trim()||null,
      employment_type:row.querySelector('.m-co-type').value||null,
      from_month:parseInt(row.querySelector('.m-co-fm').value)||null,
      from_year:parseInt(row.querySelector('.m-co-fy').value)||null,
      to_month:present?null:parseInt(row.querySelector('.m-co-tm').value)||null,
      to_year:present?null:parseInt(row.querySelector('.m-co-ty').value)||null,
      description:row.querySelector('.m-co-desc').value.trim()||null,
    };
  }).filter(c=>c.name);
  const education=[...document.querySelectorAll('#m-edu-rows .mem-entry')].map(row=>({
    institution:row.querySelector('.m-edu-inst').value.trim()||null,
    degree:row.querySelector('.m-edu-deg').value.trim()||null,
    field_of_study:row.querySelector('.m-edu-fos').value.trim()||null,
    graduation_year:parseInt(row.querySelector('.m-edu-gy').value)||null,
    gpa:row.querySelector('.m-edu-gpa').value.trim()||null,
    honors:row.querySelector('.m-edu-hon').value.trim()||null,
  })).filter(e=>e.institution);
  const certifications=[...document.querySelectorAll('#m-cert-rows .mem-entry')].map(row=>({
    name:row.querySelector('.m-cert-name').value.trim()||null,
    issuer:row.querySelector('.m-cert-issuer').value.trim()||null,
    year:parseInt(row.querySelector('.m-cert-year').value)||null,
    url:row.querySelector('.m-cert-url').value.trim()||null,
  })).filter(c=>c.name);
  const languages_spoken=[...document.querySelectorAll('#m-lang-rows .mem-entry')].map(row=>({
    language:row.querySelector('.m-lang-lang').value.trim()||null,
    proficiency:row.querySelector('.m-lang-prof').value||null,
  })).filter(l=>l.language);
  const projects=[...document.querySelectorAll('#m-projects-rows .mem-entry')].map(row=>({
    name:row.querySelector('.m-proj-name').value.trim()||null,
    role:row.querySelector('.m-proj-role').value.trim()||null,
    url:row.querySelector('.m-proj-url').value.trim()||null,
    year:parseInt(row.querySelector('.m-proj-year').value)||null,
    technologies:row.querySelector('.m-proj-tech').value.split(',').map(x=>x.trim()).filter(Boolean),
    description:row.querySelector('.m-proj-desc').value.trim()||null,
  })).filter(p=>p.name);
  const body={
    full_name:document.getElementById('m-name').value.trim()||null,
    email:document.getElementById('m-email').value.trim()||null,
    phone:document.getElementById('m-phone').value.trim()||null,
    location:document.getElementById('m-loc').value.trim()||null,
    summary:document.getElementById('m-summary').value.trim()||null,
    linkedin_url:document.getElementById('m-li').value.trim()||null,
    github_url:document.getElementById('m-gh').value.trim()||null,
    website:document.getElementById('m-web').value.trim()||null,
    portfolio_url:document.getElementById('m-portfolio').value.trim()||null,
    total_years_experience:parseInt(document.getElementById('m-yrs').value)||null,
    work_authorization:document.getElementById('m-workauth').value.trim()||null,
    target_roles:parseList(document.getElementById('m-roles').value),
    always_include_skills:parseList(document.getElementById('m-skills').value),
    availability:document.getElementById('m-availability').value.trim()||null,
    open_to_remote:document.getElementById('m-remote').checked||null,
    companies,projects,education,certifications,languages_spoken,
    personal_notes:document.getElementById('m-notes').value.trim()||null,
  };
  await fetch(`${API}/api/memory`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  closeMem();await loadMemoryChip();showToast('✓ Profile memory saved');
}

async function clearMemory(){
  if(!confirm('Clear all saved profile data?'))return;
  await fetch(`${API}/api/memory`,{method:'DELETE'});
  closeMem();await loadMemoryChip();showToast('✓ Profile memory cleared');
}

async function exportProfile(){
  try{
    const r=await fetch(`${API}/api/memory`);
    if(!r.ok)throw new Error('fetch failed');
    const m=await r.json();
    const {id,updated_at,...profile}=m;
    const name=(profile.full_name||'profile').replace(/\s+/g,'_');
    const date=new Date().toISOString().slice(0,10);
    const blob=new Blob([JSON.stringify(profile,null,2)],{type:'application/json'});
    const a=document.createElement('a');
    a.href=URL.createObjectURL(blob);
    a.download=`stackresume_profile_${name}_${date}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
    showToast('✓ Profile exported');
  }catch(e){showToast('⚠ Export failed');}
}

function importProfile(){
  const input=document.getElementById('mem-import-input');
  input.value='';
  input.click();
}

const _PROFILE_FIELDS=new Set(['full_name','email','phone','location','linkedin_url','github_url',
  'website','portfolio_url','summary','target_roles','total_years_experience','companies',
  'education','always_include_skills','certifications','languages_spoken','projects',
  'open_to_remote','work_authorization','availability','personal_notes']);

function _validateProfileJson(data){
  if(!data||typeof data!=='object'||Array.isArray(data))
    return 'File must contain a JSON object, not an array or primitive.';
  if(data.personal_info&&typeof data.personal_info==='object'&&!Array.isArray(data.personal_info))
    return 'This looks like a resume JSON, not a profile file. To load a master resume use the "Master Resume" section instead.';
  const PROFILE_ONLY=['full_name','email','phone','location','linkedin_url','github_url',
    'website','portfolio_url','summary','target_roles','total_years_experience',
    'always_include_skills','languages_spoken','open_to_remote','work_authorization',
    'availability','personal_notes'];
  const known=Object.keys(data).filter(k=>PROFILE_ONLY.includes(k));
  if(known.length===0)
    return 'No recognized profile fields found. Make sure you\'re importing a StackResume profile export file.';
  const strings=['full_name','email','phone','location','linkedin_url','github_url',
    'website','portfolio_url','summary','work_authorization','availability','personal_notes'];
  for(const f of strings){
    if(data[f]!=null&&typeof data[f]!=='string')
      return `"${f}" must be a string, got ${typeof data[f]}.`;
  }
  if(data.email&&!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email))
    return `"email" doesn't look like a valid email address.`;
  if(data.total_years_experience!=null){
    const n=Number(data.total_years_experience);
    if(!Number.isFinite(n)||!Number.isInteger(n)||n<0||n>60)
      return '"total_years_experience" must be a whole number between 0 and 60.';
  }
  if(data.open_to_remote!=null&&typeof data.open_to_remote!=='boolean')
    return '"open_to_remote" must be true or false.';
  const arrays=['target_roles','always_include_skills','companies','education','certifications','languages_spoken','projects'];
  for(const f of arrays){
    if(data[f]!=null&&!Array.isArray(data[f]))
      return `"${f}" must be an array, got ${typeof data[f]}.`;
  }
  if(Array.isArray(data.target_roles)){
    for(let i=0;i<data.target_roles.length;i++){
      if(typeof data.target_roles[i]!=='string')
        return `target_roles[${i}] must be a string.`;
    }
  }
  if(Array.isArray(data.always_include_skills)){
    for(let i=0;i<data.always_include_skills.length;i++){
      if(typeof data.always_include_skills[i]!=='string')
        return `always_include_skills[${i}] must be a string.`;
    }
  }
  if(Array.isArray(data.companies)){
    for(let i=0;i<data.companies.length;i++){
      const c=data.companies[i];
      if(!c||typeof c!=='object'||Array.isArray(c))return `companies[${i}] must be an object.`;
      if(!c.name||typeof c.name!=='string')return `companies[${i}] is missing a "name" string field.`;
    }
  }
  if(Array.isArray(data.education)){
    for(let i=0;i<data.education.length;i++){
      const e=data.education[i];
      if(!e||typeof e!=='object'||Array.isArray(e))return `education[${i}] must be an object.`;
      if(!e.institution||typeof e.institution!=='string')return `education[${i}] is missing an "institution" string field.`;
    }
  }
  if(Array.isArray(data.certifications)){
    for(let i=0;i<data.certifications.length;i++){
      const c=data.certifications[i];
      if(!c||typeof c!=='object'||Array.isArray(c))return `certifications[${i}] must be an object.`;
      if(!c.name||typeof c.name!=='string')return `certifications[${i}] is missing a "name" string field.`;
    }
  }
  if(Array.isArray(data.languages_spoken)){
    for(let i=0;i<data.languages_spoken.length;i++){
      const l=data.languages_spoken[i];
      if(!l||typeof l!=='object'||Array.isArray(l))return `languages_spoken[${i}] must be an object.`;
      if(!l.language||typeof l.language!=='string')return `languages_spoken[${i}] is missing a "language" string field.`;
    }
  }
  if(Array.isArray(data.projects)){
    for(let i=0;i<data.projects.length;i++){
      const p=data.projects[i];
      if(!p||typeof p!=='object'||Array.isArray(p))return `projects[${i}] must be an object.`;
      if(!p.name||typeof p.name!=='string')return `projects[${i}] is missing a "name" string field.`;
      if(p.technologies!=null&&!Array.isArray(p.technologies))return `projects[${i}].technologies must be an array.`;
    }
  }
  return null;
}

async function handleProfileImport(e){
  const file=e.target.files[0];if(!file)return;
  try{
    const text=await file.text();
    let data;
    try{data=JSON.parse(text);}catch{throw new Error('File is not valid JSON.');}
    const err=_validateProfileJson(data);
    if(err)throw new Error(err);
    const body=Object.fromEntries(Object.entries(data).filter(([k])=>_PROFILE_FIELDS.has(k)));
    const r=await fetch(`${API}/api/memory`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    if(!r.ok)throw new Error('Server rejected the import. Please try again.');
    await openMemory();
    await loadMemoryChip();
    showToast('✓ Profile imported');
  }catch(err){showToast('⚠ '+err.message);}
  e.target.value='';
}
