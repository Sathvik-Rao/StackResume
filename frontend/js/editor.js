// ── Resume Sections Editor ─────────────────────────────────────────────────
function _vid(msgId){return `v${msgId.replace(/-/g,'')}`;}

// Entry point — invoked when the user opens the Edit tab. Initializes the
// buffered copy ONCE; subsequent add/remove/update operations call _edRerender
// which re-uses the buffer (preserving in-flight edits).
function renderEditor(msgId){
  const vid=_vid(msgId);
  const host=document.getElementById(`${vid}-edit-body`);
  if(!host)return;
  const r=window[`__r_${msgId}`];
  if(!r){host.innerHTML='<div class="pv-empty">No resume to edit.</div>';return;}
  if(!window[`__edit_${msgId}`]){
    // Normalize the working copy so char-split garbage is presented to the
    // user as a real, editable list rather than 80 single-char rows (which
    // also blew up the str-section renderer when the value was a bare string).
    window[`__edit_${msgId}`]=normalizeResume(JSON.parse(JSON.stringify(r)));
  }
  host.innerHTML=_editorHtml(msgId);
}

// Discard unsaved edits and reload the saved version.
function revertEditor(msgId){
  const r=window[`__r_${msgId}`];
  if(!r)return;
  window[`__edit_${msgId}`]=normalizeResume(JSON.parse(JSON.stringify(r)));
  const host=document.getElementById(`${_vid(msgId)}-edit-body`);
  if(host)host.innerHTML=_editorHtml(msgId);
  showToast('Reverted to saved version');
}

// Re-render the editor markup from the existing buffer (does NOT reset state).
// After re-render, focus the input that was just added if `_edFocusNext` is set.
function _edRerender(msgId){
  const host=document.getElementById(`${_vid(msgId)}-edit-body`);
  if(!host)return;
  host.innerHTML=_editorHtml(msgId);
  if(window._edFocusNext){
    const sel=window._edFocusNext;window._edFocusNext=null;
    const el=host.querySelector(sel);
    if(el){el.focus();if(el.select)el.select();el.scrollIntoView({block:'nearest',behavior:'smooth'});}
  }
}

// ── Section schema ────────────────────────────────────────────────────────
// Definitions for every list-of-objects section. `fields` describes each
// editable input; `bullets` lists keys that are arrays of strings; `defaults`
// is the blank shape used when adding a new entry.
const _ED_OBJ_SECTIONS={
  experience:{
    label:'Experience', singular:'role',
    fields:[
      {k:'title',label:'Title'},
      {k:'company',label:'Company'},
      {k:'start_date',label:'Start'},
      {k:'end_date',label:'End',placeholder:'Present'},
      {k:'location',label:'Location'},
      {k:'employment_type',label:'Type',placeholder:'Full-time'},
      {k:'team_size',label:'Team size'},
    ],
    csv:[{k:'technologies',label:'Technologies'}],
    bullets:[
      {k:'responsibilities',label:'Responsibilities'},
      {k:'achievements',label:'Achievements'},
    ],
    defaults:{title:'',company:'',start_date:'',end_date:'',location:'',employment_type:'',team_size:'',technologies:[],responsibilities:[],achievements:[]},
  },
  education:{
    label:'Education', singular:'degree',
    fields:[
      {k:'institution',label:'Institution'},
      {k:'degree',label:'Degree'},
      {k:'field_of_study',label:'Field of study'},
      {k:'location',label:'Location'},
      {k:'start_date',label:'Start'},
      {k:'end_date',label:'End'},
      {k:'gpa',label:'GPA'},
      {k:'honors',label:'Honors'},
    ],
    csv:[
      {k:'relevant_coursework',label:'Coursework'},
      {k:'activities',label:'Activities'},
    ],
    bullets:[],
    defaults:{institution:'',degree:'',field_of_study:'',start_date:'',end_date:'',gpa:'',honors:'',location:'',relevant_coursework:[],activities:[]},
  },
  projects:{
    label:'Projects', singular:'project',
    fields:[
      {k:'name',label:'Name'},
      {k:'role',label:'Role'},
      {k:'type',label:'Type',placeholder:'Personal / Open Source / Work / Academic'},
      {k:'start_date',label:'Start'},
      {k:'end_date',label:'End'},
      {k:'url',label:'URL'},
      {k:'github',label:'GitHub'},
      {k:'description',label:'Description',textarea:true,full:true},
    ],
    csv:[{k:'technologies',label:'Technologies'}],
    bullets:[{k:'highlights',label:'Highlights'}],
    defaults:{name:'',role:'',type:'',start_date:'',end_date:'',description:'',url:'',github:'',technologies:[],highlights:[]},
  },
  open_source_contributions:{
    label:'Open Source', singular:'contribution',
    fields:[
      {k:'project',label:'Project'},
      {k:'role',label:'Role'},
      {k:'url',label:'URL'},
      {k:'stars',label:'Stars'},
      {k:'language',label:'Language'},
      {k:'description',label:'Description',textarea:true,full:true},
    ],
    csv:[],
    bullets:[{k:'contributions',label:'Contributions'}],
    defaults:{project:'',role:'',url:'',stars:'',language:'',description:'',contributions:[]},
  },
  certifications:{
    label:'Certifications', singular:'certification',
    fields:[
      {k:'name',label:'Name'},
      {k:'issuer',label:'Issuer'},
      {k:'date',label:'Issued'},
      {k:'expiry',label:'Expires'},
      {k:'credential_id',label:'Credential ID'},
      {k:'url',label:'URL'},
    ],
    csv:[],bullets:[],
    defaults:{name:'',issuer:'',date:'',expiry:'',credential_id:'',url:''},
  },
  publications:{
    label:'Publications', singular:'publication',
    fields:[
      {k:'title',label:'Title'},
      {k:'venue',label:'Venue'},
      {k:'date',label:'Date'},
      {k:'type',label:'Type',placeholder:'Article / Conference / Journal'},
      {k:'url',label:'URL'},
    ],
    csv:[{k:'authors',label:'Authors'}],
    bullets:[],
    defaults:{title:'',venue:'',date:'',type:'',url:'',authors:[]},
  },
  patents:{
    label:'Patents', singular:'patent',
    fields:[
      {k:'title',label:'Title'},
      {k:'patent_number',label:'Patent #'},
      {k:'date',label:'Date'},
      {k:'url',label:'URL'},
      {k:'description',label:'Description',textarea:true,full:true},
    ],
    csv:[],bullets:[],
    defaults:{title:'',patent_number:'',date:'',url:'',description:''},
  },
  volunteer_experience:{
    label:'Volunteer Experience', singular:'role',
    fields:[
      {k:'role',label:'Role'},
      {k:'organization',label:'Organization'},
      {k:'start_date',label:'Start'},
      {k:'end_date',label:'End'},
      {k:'description',label:'Description',textarea:true,full:true},
    ],
    csv:[],bullets:[],
    defaults:{role:'',organization:'',start_date:'',end_date:'',description:''},
  },
  languages:{
    label:'Languages', singular:'language',
    fields:[
      {k:'language',label:'Language'},
      {k:'proficiency',label:'Proficiency',placeholder:'Native / Fluent / Professional / Conversational / Basic'},
    ],
    csv:[],bullets:[],
    defaults:{language:'',proficiency:''},
  },
};

// Simple string-array sections.
const _ED_STR_SECTIONS=[
  {k:'core_competencies',label:'Core Competencies',singular:'competency',placeholder:'e.g. Distributed systems'},
  {k:'awards_and_honors',label:'Awards & Honors',singular:'award',placeholder:'e.g. Best Paper, ICSE 2024'},
  {k:'interests',label:'Interests',singular:'interest',placeholder:'e.g. Hiking'},
];

function _editorHtml(msgId){
  const e=window[`__edit_${msgId}`]||{};
  const meta=e.metadata||{};
  const pi=e.personal_info||{};
  const tsk=e.technical_skills||{};
  const edited=meta.manually_edited?`<span class="ed-badge">${ico('ic-edit-pencil')} Manually edited · v${meta.manual_edit_count||1}</span>`:'';
  const lastScore=meta.overall_score!=null?`Last score: <strong>${Math.round(meta.overall_score)}/100</strong>`:'';

  const personal=`
    <div class="ed-sec">
      <div class="ed-sec-hd">Personal Info</div>
      ${_edTextRow(msgId,'Full name','personal_info.full_name',pi.full_name)}
      ${_edTextRow(msgId,'Title','personal_info.professional_title',pi.professional_title)}
      <div class="ed-grid2">
        ${_edTextRow(msgId,'Email','personal_info.email',pi.email)}
        ${_edTextRow(msgId,'Phone','personal_info.phone',pi.phone)}
        ${_edTextRow(msgId,'Location','personal_info.location',pi.location)}
        ${_edTextRow(msgId,'LinkedIn','personal_info.linkedin',pi.linkedin)}
        ${_edTextRow(msgId,'GitHub','personal_info.github',pi.github)}
        ${_edTextRow(msgId,'Website','personal_info.website',pi.website)}
        ${_edTextRow(msgId,'Portfolio','personal_info.portfolio',pi.portfolio)}
      </div>
    </div>`;

  const summary=`
    <div class="ed-sec">
      <div class="ed-sec-hd">Professional Summary</div>
      <textarea class="fta" style="min-height:90px"
        oninput="_edSet('${msgId}','professional_summary',this.value)">${esc(e.professional_summary||'')}</textarea>
    </div>`;

  // Core competencies, awards, interests — all simple string arrays.
  const strSecs=_ED_STR_SECTIONS.map(cfg=>_edStrSectionHtml(msgId,cfg,e[cfg.k]||[])).join('');

  // Experience, education, projects, open source, certifications, publications,
  // patents, volunteer, languages — full object editors.
  const objSecs=Object.keys(_ED_OBJ_SECTIONS).map(key=>{
    const cfg=_ED_OBJ_SECTIONS[key];
    return _edObjSectionHtml(msgId,key,cfg,e[key]||[]);
  }).join('');

  const skillCats=[
    ['programming_languages','Programming Languages'],
    ['frameworks_and_libraries','Frameworks & Libraries'],
    ['databases','Databases'],
    ['cloud_and_infrastructure','Cloud & Infrastructure'],
    ['devops_and_tools','DevOps & Tooling'],
    ['testing','Testing'],
    ['methodologies','Methodologies'],
    ['soft_skills','Soft Skills'],
  ];
  const skillsHtml=`
    <div class="ed-sec">
      <div class="ed-sec-hd">Technical Skills <span style="font-size:10.5px;color:var(--text3);font-weight:400;text-transform:none;letter-spacing:0">comma-separated</span></div>
      ${skillCats.map(([k,label])=>`
        <div class="ed-row">
          <div class="fl">${label}</div>
          <input class="fi" type="text" value="${esc((tsk[k]||[]).join(', '))}"
            oninput="_edSetCsv('${msgId}','technical_skills.${k}',this.value)">
        </div>`).join('')}
    </div>`;

  // References — single textarea. Stored as a string (the typical
  // "Available upon request" case) so the preview & all PDF generators,
  // which already handle string|list, render correctly without changes.
  const refsVal=typeof e.references==='string'
    ? e.references
    : (Array.isArray(e.references)?e.references.filter(Boolean).join('\n'):'');
  const referencesHtml=`
    <div class="ed-sec">
      <div class="ed-sec-hd">References</div>
      <textarea class="fta" style="min-height:60px" placeholder="e.g. Available upon request"
        oninput="_edSet('${msgId}','references',this.value)">${esc(refsVal)}</textarea>
    </div>`;

  return `<div class="ed-wrap">
    <div class="ed-bar">
      <div class="ed-bar-l">
        ${edited||'<span style="color:var(--text3)">Add / edit / remove any section, then save &amp; re-score.</span>'}
        ${lastScore?`<span style="color:var(--text3)">${lastScore}</span>`:''}
      </div>
      <div class="ed-bar-r">
        <button class="ibtn" onclick="revertEditor('${msgId}')" title="Discard unsaved changes">${ico('ic-refresh')} Revert</button>
        ${msgId==='__master'?'':`<button class="ibtn" onclick="rescoreResume('${msgId}')" title="Save and re-run the Quality Reviewer">🎯 Save &amp; Re-score</button>`}
        <button class="ibtn pri" onclick="saveResumeEdits('${msgId}')">💾 Save edits</button>
      </div>
    </div>
    ${personal}
    ${summary}
    ${strSecs}
    ${objSecs}
    ${skillsHtml}
    ${referencesHtml}
  </div>`;
}

// ── HTML builders ─────────────────────────────────────────────────────────
function _edTextRow(msgId,label,path,value){
  return `<div class="ed-row">
    <div class="fl">${label}</div>
    <input class="fi" type="text" value="${esc(value||'')}" oninput="_edSet('${msgId}','${path}',this.value)">
  </div>`;
}

function _edStrSectionHtml(msgId,cfg,arr){
  // Defensive: backend sometimes hands us a string ("Hiking, Reading") or null
  // for fields that are supposed to be lists. toArr handles both shapes plus
  // the char-split degenerate case, so the .map below never explodes.
  arr=toArr(arr);
  const items=arr.map((v,i)=>`<div class="ed-bullet-row" data-idx="${i}">
    <textarea class="fta" data-fld="${cfg.k}-${i}" placeholder="${esc(cfg.placeholder||'')}"
      oninput="_edStrSet('${msgId}','${cfg.k}',${i},this.value)">${esc(v||'')}</textarea>
    <button class="ed-rm" onclick="_edStrRm('${msgId}','${cfg.k}',${i})" title="Remove">×</button>
  </div>`).join('')||`<div class="pv-empty">No ${cfg.singular} yet — click "+ Add" to create one.</div>`;
  return `<div class="ed-sec">
    <div class="ed-sec-hd">${cfg.label}
      <div class="ed-sec-hd-r">
        <button class="ed-add-btn" onclick="_edStrAdd('${msgId}','${cfg.k}')">+ Add ${cfg.singular}</button>
      </div>
    </div>
    ${items}
  </div>`;
}

function _edObjSectionHtml(msgId,key,cfg,arr){
  if(!Array.isArray(arr))arr=arr?[arr]:[];
  const items=arr.map((x,i)=>_edObjItem(msgId,key,cfg,i,x)).join('')
    ||`<div class="pv-empty">No ${cfg.singular} yet — click "+ Add ${cfg.singular}" to create one.</div>`;
  return `<div class="ed-sec">
    <div class="ed-sec-hd">${cfg.label}
      <div class="ed-sec-hd-r">
        <button class="ed-add-btn" onclick="_edObjAdd('${msgId}','${key}')">+ Add ${cfg.singular}</button>
      </div>
    </div>
    ${items}
  </div>`;
}

function _edObjItem(msgId,key,cfg,idx,x){
  // Bad LLM payloads sometimes give us a string ("Author A, Author B") where a
  // dict was expected. Coerce to an empty dict so the field renderers below
  // don't blow up with `undefined.foo`.
  if(!x||typeof x!=='object'||Array.isArray(x))x={};
  const moveUp=idx>0?`<button class="ed-rm" onclick="_edObjMove('${msgId}','${key}',${idx},-1)" title="Move up">↑</button>`:'';
  const moveDown=`<button class="ed-rm" onclick="_edObjMove('${msgId}','${key}',${idx},1)" title="Move down">↓</button>`;

  // Split fields into full-width (textareas) and grid items.
  const fullFields=cfg.fields.filter(f=>f.full);
  const gridFields=cfg.fields.filter(f=>!f.full);

  const gridHtml=gridFields.map(f=>`<div class="ed-row">
    <div class="fl">${f.label}</div>
    ${f.textarea
      ? `<textarea class="fta" data-fld="${key}-${idx}-${f.k}" placeholder="${esc(f.placeholder||'')}"
           oninput="_edObjSet('${msgId}','${key}',${idx},'${f.k}',this.value)">${esc(x[f.k]||'')}</textarea>`
      : `<input class="fi" type="text" data-fld="${key}-${idx}-${f.k}" value="${esc(x[f.k]||'')}" placeholder="${esc(f.placeholder||'')}"
           oninput="_edObjSet('${msgId}','${key}',${idx},'${f.k}',this.value)">`}
  </div>`).join('');

  const fullHtml=fullFields.map(f=>`<div class="ed-row" style="grid-template-columns:140px 1fr">
    <div class="fl">${f.label}</div>
    <textarea class="fta" data-fld="${key}-${idx}-${f.k}" placeholder="${esc(f.placeholder||'')}"
      oninput="_edObjSet('${msgId}','${key}',${idx},'${f.k}',this.value)">${esc(x[f.k]||'')}</textarea>
  </div>`).join('');

  const csvHtml=(cfg.csv||[]).map(f=>`<div class="ed-row" style="grid-template-columns:140px 1fr">
    <div class="fl">${f.label}</div>
    <input class="fi" type="text" value="${esc(toArr(x[f.k]).join(', '))}"
      oninput="_edObjSetCsv('${msgId}','${key}',${idx},'${f.k}',this.value)">
  </div>`).join('');

  const bulletsHtml=(cfg.bullets||[]).map(f=>{
    const arr=toArr(x[f.k]);
    const rows=arr.map((b,bi)=>`<div class="ed-bullet-row">
      <textarea class="fta" data-fld="${key}-${idx}-${f.k}-${bi}"
        oninput="_edObjBulletSet('${msgId}','${key}',${idx},'${f.k}',${bi},this.value)">${esc(b||'')}</textarea>
      <button class="ed-rm" onclick="_edObjBulletRm('${msgId}','${key}',${idx},'${f.k}',${bi})">×</button>
    </div>`).join('')||'<div class="pv-empty" style="font-size:11.5px">No items.</div>';
    return `<div style="margin-top:10px">
      <div class="fl" style="display:flex;justify-content:space-between;align-items:center">
        <span>${f.label}</span>
        <button class="ed-add-btn" onclick="_edObjBulletAdd('${msgId}','${key}',${idx},'${f.k}')">+ Add bullet</button>
      </div>
      ${rows}
    </div>`;
  }).join('');

  return `<div class="ed-list-item" data-idx="${idx}">
    <div class="ed-il-actions">
      ${moveUp}${moveDown}
      <button class="ed-rm" onclick="_edObjRm('${msgId}','${key}',${idx})" title="Remove">× Remove</button>
    </div>
    <div class="ed-grid2">${gridHtml}</div>
    ${fullHtml}
    ${csvHtml}
    ${bulletsHtml}
  </div>`;
}

// ── Buffered state helpers ───────────────────────────────────────────────
function _edRef(msgId){return window[`__edit_${msgId}`]||(window[`__edit_${msgId}`]={});}
function _setByPath(obj,path,val){
  const parts=path.split('.');let cur=obj;
  for(let i=0;i<parts.length-1;i++){
    const k=parts[i];if(cur[k]==null||typeof cur[k]!=='object')cur[k]={};cur=cur[k];
  }
  cur[parts[parts.length-1]]=val;
}
function _edSet(msgId,path,val){_setByPath(_edRef(msgId),path,val);}
function _edSetCsv(msgId,path,val){
  _setByPath(_edRef(msgId),path,val.split(',').map(s=>s.trim()).filter(Boolean));
}

// String-array section helpers (core_competencies, awards, interests).
function _edStrAdd(msgId,key){
  const e=_edRef(msgId);if(!Array.isArray(e[key]))e[key]=[];
  e[key].push('');
  window._edFocusNext=`[data-fld="${key}-${e[key].length-1}"]`;
  _edRerender(msgId);
}
function _edStrSet(msgId,key,idx,val){
  const e=_edRef(msgId);if(!Array.isArray(e[key]))e[key]=[];
  e[key][idx]=val;
}
function _edStrRm(msgId,key,idx){
  const e=_edRef(msgId);if(!Array.isArray(e[key]))return;
  e[key].splice(idx,1);_edRerender(msgId);
}

// Object-array section helpers.
function _edObjAdd(msgId,key){
  const cfg=_ED_OBJ_SECTIONS[key];if(!cfg)return;
  const e=_edRef(msgId);if(!Array.isArray(e[key]))e[key]=[];
  e[key].push(JSON.parse(JSON.stringify(cfg.defaults)));
  const newIdx=e[key].length-1;
  const firstField=(cfg.fields[0]||{}).k;
  if(firstField)window._edFocusNext=`[data-fld="${key}-${newIdx}-${firstField}"]`;
  _edRerender(msgId);
}
function _edObjRm(msgId,key,idx){
  const e=_edRef(msgId);if(!Array.isArray(e[key]))return;
  e[key].splice(idx,1);_edRerender(msgId);
}
function _edObjMove(msgId,key,idx,delta){
  const e=_edRef(msgId);if(!Array.isArray(e[key]))return;
  const j=idx+delta;if(j<0||j>=e[key].length)return;
  const tmp=e[key][idx];e[key][idx]=e[key][j];e[key][j]=tmp;
  _edRerender(msgId);
}
function _edObjSet(msgId,key,idx,fld,val){
  const e=_edRef(msgId);if(!e[key]||!e[key][idx])return;
  e[key][idx][fld]=val;
}
function _edObjSetCsv(msgId,key,idx,fld,val){
  const e=_edRef(msgId);if(!e[key]||!e[key][idx])return;
  e[key][idx][fld]=val.split(',').map(s=>s.trim()).filter(Boolean);
}
function _edObjBulletAdd(msgId,key,idx,fld){
  const e=_edRef(msgId);if(!e[key]||!e[key][idx])return;
  e[key][idx][fld]=e[key][idx][fld]||[];
  e[key][idx][fld].push('');
  window._edFocusNext=`[data-fld="${key}-${idx}-${fld}-${e[key][idx][fld].length-1}"]`;
  _edRerender(msgId);
}
function _edObjBulletSet(msgId,key,idx,fld,bi,val){
  const e=_edRef(msgId);if(!e[key]||!e[key][idx]||!e[key][idx][fld])return;
  e[key][idx][fld][bi]=val;
}
function _edObjBulletRm(msgId,key,idx,fld,bi){
  const e=_edRef(msgId);if(!e[key]||!e[key][idx]||!e[key][idx][fld])return;
  e[key][idx][fld].splice(bi,1);_edRerender(msgId);
}

async function saveResumeEdits(msgId,silent){
  const edited=window[`__edit_${msgId}`];
  if(!edited){showToast('Nothing to save');return;}
  if(msgId==='__master')return _saveMasterEdits(edited,silent);
  try{
    const r=await fetch(`${API}/api/messages/${msgId}/resume`,{
      method:'PATCH',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({resume_json:edited}),
    });
    if(!r.ok){const e=await r.json().catch(()=>({detail:'Save failed'}));throw new Error(e.detail||'Save failed');}
    const m=await r.json();
    window[`__r_${msgId}`]=m.resume_json;
    // Re-seed the buffer from the server response so manually_edited /
    // manual_edit_count / last_manually_edited_at land in the buffer too.
    window[`__edit_${msgId}`]=JSON.parse(JSON.stringify(m.resume_json));
    _refreshMsgViewer(msgId);
    if(!silent)showToast('✓ Resume edits saved');
    return m;
  }catch(e){showToast('⚠️ '+e.message);}
}

async function rescoreResume(msgId){
  // Save buffered edits first (if any), then re-run the Quality Reviewer.
  const saved=await saveResumeEdits(msgId,true);
  if(!saved)return;
  showToast('🎯 Re-scoring…');
  try{
    const r=await fetch(`${API}/api/messages/${msgId}/rescore`,{method:'POST'});
    if(!r.ok){const e=await r.json().catch(()=>({detail:'Rescore failed'}));throw new Error(e.detail||'Rescore failed');}
    const m=await r.json();
    window[`__r_${msgId}`]=m.resume_json;
    _refreshMsgViewer(msgId);
    const sc=(m.resume_json?.metadata?.overall_score)||0;
    showToast(`✓ New score: ${Math.round(sc)}/100`);
  }catch(e){showToast('⚠️ '+e.message);}
}

// Re-render the message's preview, JSON, and editor so the new resume shows everywhere.
function _refreshMsgViewer(msgId){
  const vid=_vid(msgId);
  const r=window[`__r_${msgId}`];
  if(!r)return;
  const pv=document.getElementById(`${vid}-pv`);
  if(pv)pv.innerHTML=buildPv(r);
  const raw=document.getElementById(`${vid}-raw`);
  if(raw)raw.innerHTML=`<pre class="jp">${synHl(r)}</pre>`;
  const edBody=document.getElementById(`${vid}-edit-body`);
  // Re-render the editor markup from the (possibly just re-seeded) buffer.
  if(edBody && edBody.children.length)_edRerender(msgId);
  // Refresh the score row + edited badge at the top of the message bubble.
  _refreshScoreRow(msgId,r);
  _refreshEditedBadge(msgId,r);
}
function _refreshScoreRow(msgId,r){
  // Find the message container that holds this viewer and rebuild the score row.
  const vid=_vid(msgId);
  const viewer=document.getElementById(`${vid}-pv`)?.closest('.at-wrap, .at, .msg, .ai, .ai-content, .jv')?.parentElement;
  const meta=r?.metadata||{};
  // The score row is the closest .score-row before the viewer; if present, swap.
  let host=document.getElementById(`${vid}-pv`)?.closest('.jv');
  let target=host?.previousElementSibling;
  while(target && !target.classList.contains('score-row')){target=target.previousElementSibling;}
  if(target && meta.overall_score!=null){
    target.innerHTML = sc('Overall',meta.overall_score)+sc('ATS',meta.ats_score)+
      sc('Quality',meta.quality_score)+sc('Impact',meta.impact_score)+
      sc('Complete',meta.completeness_score)+
      (meta.jd_match_score?`<div class="sb2 jdm">${ico('ic-target')} JD Match <strong>${Math.round(meta.jd_match_score)}</strong></div>`:'');
  }
}
function _refreshEditedBadge(msgId,r){
  const vid=_vid(msgId);
  const jvl=document.getElementById(`${vid}-pv`)?.closest('.jv')?.querySelector('.jv-l');
  if(!jvl)return;
  // Remove any existing badge then re-insert if needed.
  jvl.querySelectorAll('.ed-badge').forEach(b=>b.remove());
  if(r?.metadata?.manually_edited){
    const span=document.createElement('span');
    span.className='ed-badge';
    span.title='This resume has been manually edited';
    span.innerHTML=`${ico('ic-edit-pencil')} Edited`;
    // Insert right after the title, before the tabs row.
    const title=jvl.querySelector('.jv-title');
    if(title)title.after(span); else jvl.prepend(span);
  }
}
function openClExport(msgId){
  const r=window[`__r_${msgId}`];const t=window[`__cl_${msgId}`];
  if(!r||!t)return;
  pdfResume=r;
  exportKind='coverletter';exportClMsgId=msgId;
  _pdfFromMaster=false;
  document.getElementById('export-title').textContent='✉️ Export Cover Letter';
  // Page count doesn't apply to cover letters — they're always one page.
  document.getElementById('pages-fg').style.display='none';
  document.getElementById('pdf-modal').classList.add('open');
  updateExportPreview();
}
