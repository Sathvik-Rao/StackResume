// ── Master Resumes (multiple, named) ─────────────────────────────────────────
// Backed by /api/memory/master-resumes. Each item has {id, name, resume,
// is_default, created_at, updated_at}. The chat editor and PDF export operate
// on the currently-SELECTED item in the master modal; the chat "Use Master"
// button attaches by name from a dropdown picker.
let _masterResumes=[];
let _selectedMasterId=null;
let _vmNameDirty=false;
let _pdfFromMaster=false;
// File-input intent: 'new' uploads as a new master, 'replace' overwrites one.
let _masterFileMode={kind:'new'};

async function loadMasterResumes(){
  try{
    const r=await fetch(`${API}/api/memory/master-resumes`);
    if(!r.ok)return;
    const d=await r.json();
    _masterResumes=d.items||[];
    // Keep current selection if still present, else default, else first.
    if(_selectedMasterId && !_masterResumes.find(it=>it.id===_selectedMasterId))_selectedMasterId=null;
    if(!_selectedMasterId)_selectedMasterId=(_defaultMaster()||{}).id||null;
    _updateMasterUI();
  }catch(e){}
}

function _selectedMaster(){return _masterResumes.find(it=>it.id===_selectedMasterId)||null;}
function _defaultMaster(){return _masterResumes.find(it=>it.is_default)||_masterResumes[0]||null;}

function _updateMasterUI(){
  const has=_masterResumes.length>0;
  // Input bar "Use Master" button
  const attachBtn=document.getElementById('master-attach-btn');
  if(attachBtn)attachBtn.style.display=has?'':'none';
  // Sidebar footer badge
  const badge=document.getElementById('master-sb-badge');
  if(badge)badge.style.display=has?'':'none';
  // Data Management section
  const dmTitle=document.getElementById('dm-master-title');
  if(dmTitle){
    if(!has)dmTitle.textContent='No master resumes saved';
    else if(_masterResumes.length===1)dmTitle.textContent=_masterResumes[0].name||'Master Resume';
    else dmTitle.textContent=`${_masterResumes.length} master resumes saved`;
  }
  // Refresh open modal
  if(document.getElementById('view-master-modal').classList.contains('open'))_renderMasterModal();
  if(!has)_hideMasterAttachMenu();
}

function _renderMasterModal(){
  const empty=document.getElementById('vm-empty');
  const saved=document.getElementById('vm-saved');
  if(_masterResumes.length===0){
    if(empty)empty.style.display='';
    if(saved){saved.style.display='none';}
    delete window['__r___master'];
    delete window['__edit___master'];
    return;
  }
  if(empty)empty.style.display='none';
  if(saved){saved.style.display='flex';}

  // List
  const listEl=document.getElementById('vm-list');
  const countEl=document.getElementById('vm-count');
  if(countEl)countEl.textContent=String(_masterResumes.length);
  if(listEl){
    listEl.innerHTML=_masterResumes.map(it=>{
      const sel=(it.id===_selectedMasterId);
      const def=it.is_default;
      return `<button class="vm-li${sel?' sel':''}" onclick="selectMaster('${it.id}')" data-id="${it.id}" title="${esc(it.name||'')}">
        <span class="vm-li-star" title="${def?'Default':''}">${def?'⭐':'☆'}</span>
        <span class="vm-li-name">${esc(it.name||'Untitled')}</span>
      </button>`;
    }).join('');
  }

  // Right pane (selected item)
  const sel=_selectedMaster();
  if(!sel)return;
  const r=sel.resume||{};
  // Seed shared window keys so the editor/refresh helpers (keyed by msgId) work.
  window['__r___master']=r;
  // Reset the editor buffer so it tracks the freshly-selected resume.
  delete window['__edit___master'];

  const nameInput=document.getElementById('vm-name-input');
  if(nameInput && document.activeElement!==nameInput){nameInput.value=sel.name||'';_vmNameDirty=false;}
  const defBtn=document.getElementById('vm-default-btn');
  if(defBtn){defBtn.textContent=sel.is_default?'⭐ Default':'☆ Set default';defBtn.disabled=!!sel.is_default;defBtn.style.opacity=sel.is_default?0.7:1;}
  const nameEl=document.getElementById('vm-name');
  const roleEl=document.getElementById('vm-role');
  if(nameEl)nameEl.textContent=r.personal_info?.full_name||'';
  if(roleEl)roleEl.textContent=r.personal_info?.professional_title||r.metadata?.jd_role||'';
  const body=document.getElementById('vm-body');
  if(body){
    const msgId='__master',vid='v__master';
    const editedBadge=(r?.metadata?.manually_edited)
      ? `<span class="ed-badge" title="This resume has been manually edited">${ico('ic-edit-pencil')} Edited</span>`
      : '';
    body.innerHTML=`<div class="jv-tb">
      <div class="jv-l">
        ${editedBadge}
        <div class="tabs">
          <button class="jtab on" data-tab="pv" onclick="swTab('${vid}','pv',this)">${ico('ic-doc')} Preview</button>
          <button class="jtab" data-tab="edit" onclick="swTab('${vid}','edit',this);renderEditor('${msgId}')">${ico('ic-edit-pencil')} Edit</button>
          <button class="jtab" data-tab="raw" onclick="swTab('${vid}','raw',this)">{ } JSON</button>
        </div>
      </div>
    </div>
    <div class="jvb" id="${vid}-pv" style="padding:12px">${buildPv(r)}</div>
    <div class="jvb" id="${vid}-edit" style="display:none;padding:12px"><div id="${vid}-edit-body"></div></div>
    <div class="jvb" id="${vid}-raw" style="display:none;padding:12px"><pre class="jp">${synHl(r)}</pre></div>`;
  }
}

function selectMaster(id){
  if(_selectedMasterId===id)return;
  _selectedMasterId=id;
  _renderMasterModal();
}

function openMasterModal(){
  // Pick a sensible default selection if none yet.
  if(!_selectedMaster())_selectedMasterId=(_defaultMaster()||{}).id||null;
  _renderMasterModal();
  document.getElementById('view-master-modal').classList.add('open');
}
function viewMasterResume(){openMasterModal();}
function closeViewMaster(){document.getElementById('view-master-modal').classList.remove('open');}
document.getElementById('view-master-modal').addEventListener('click',e=>{if(e.target===e.currentTarget)closeViewMaster();});

function downloadMasterJson(){
  const sel=_selectedMaster();if(!sel){showToast('No master resume selected');return;}
  const blob=new Blob([JSON.stringify(sel.resume,null,2)],{type:'application/json'});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);
  a.download=`master_${(sel.name||'resume').replace(/[\s\\/]+/g,'_')}.json`;
  a.click();
}

function copyMasterJson(){
  const sel=_selectedMaster();
  if(!sel){showToast('No master resume selected');return;}
  navigator.clipboard.writeText(JSON.stringify(sel.resume,null,2));
  showToast('✓ Copied to clipboard');
}

function openMasterPdf(){
  const sel=_selectedMaster();
  if(!sel){showToast('No master resume selected');return;}
  pdfResume=sel.resume;
  exportKind='resume';exportClMsgId=null;
  _pdfFromMaster=true;
  document.getElementById('export-title').textContent=`📄 Export — ${sel.name}`;
  document.getElementById('pages-fg').style.display='';
  closeViewMaster();
  document.getElementById('pdf-modal').classList.add('open');
  updateExportPreview();
}

async function renameSelectedMaster(){
  const sel=_selectedMaster();if(!sel)return;
  if(!_vmNameDirty)return;
  const input=document.getElementById('vm-name-input');
  if(!input)return;
  const next=input.value.trim();
  _vmNameDirty=false;
  if(!next){input.value=sel.name||'';return;}
  if(next===sel.name)return;
  try{
    const r=await fetch(`${API}/api/memory/master-resumes/${sel.id}`,{
      method:'PUT',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({name:next}),
    });
    if(!r.ok){const e=await r.json().catch(()=>({detail:'Rename failed'}));throw new Error(e.detail||'Rename failed');}
    const updated=await r.json();
    const idx=_masterResumes.findIndex(it=>it.id===sel.id);
    if(idx>=0)_masterResumes[idx]=updated;
    _updateMasterUI();
    showToast('✓ Renamed');
  }catch(e){showToast('⚠ '+e.message);}
}

async function setSelectedMasterDefault(){
  const sel=_selectedMaster();if(!sel||sel.is_default)return;
  try{
    const r=await fetch(`${API}/api/memory/master-resumes/${sel.id}`,{
      method:'PUT',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({is_default:true}),
    });
    if(!r.ok)throw new Error('Failed to set default');
    await loadMasterResumes();
    showToast(`⭐ Default: ${sel.name}`);
  }catch(e){showToast('⚠ '+e.message);}
}

async function deleteSelectedMaster(){
  const sel=_selectedMaster();if(!sel)return;
  if(!confirm(`Delete master resume "${sel.name}"?`))return;
  try{
    const r=await fetch(`${API}/api/memory/master-resumes/${sel.id}`,{method:'DELETE'});
    if(!r.ok&&r.status!==204)throw new Error('Delete failed');
    _selectedMasterId=null;
    await loadMasterResumes();
    showToast('✓ Deleted');
  }catch(e){showToast('⚠ '+e.message);}
}

function replaceSelectedMaster(){
  const sel=_selectedMaster();if(!sel)return;
  _masterFileMode={kind:'replace',id:sel.id};
  document.getElementById('master-file-input').click();
}

function _validateResumeJson(data){
  if(!data||typeof data!=='object'||Array.isArray(data))
    return 'File must contain a JSON object, not an array or primitive.';
  if(!data.personal_info||typeof data.personal_info!=='object'||Array.isArray(data.personal_info))
    return 'This doesn\'t look like a resume file — missing "personal_info" object. Make sure you\'re importing a StackResume-generated resume JSON.';
  const pi=data.personal_info;
  if(pi.full_name!=null&&typeof pi.full_name!=='string')
    return '"personal_info.full_name" must be a string.';
  if(pi.email!=null&&typeof pi.email!=='string')
    return '"personal_info.email" must be a string.';
  const resumeArrays=['experience','education','certifications','projects','skills','core_competencies'];
  for(const f of resumeArrays){
    if(data[f]!=null&&!Array.isArray(data[f]))
      return `"${f}" must be an array, got ${typeof data[f]}.`;
  }
  return null;
}

async function handleMasterFile(e){
  const file=e.target.files[0];
  const mode=_masterFileMode;_masterFileMode={kind:'new'};
  if(!file)return;
  try{
    const text=await file.text();
    let resume;
    try{resume=JSON.parse(text);}catch{throw new Error('File is not valid JSON.');}
    const err=_validateResumeJson(resume);
    if(err)throw new Error(err);
    if(mode.kind==='replace' && mode.id){
      const r=await fetch(`${API}/api/memory/master-resumes/${mode.id}`,{
        method:'PUT',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({resume}),
      });
      if(!r.ok){const ej=await r.json().catch(()=>({detail:'Replace failed'}));throw new Error(ej.detail||'Replace failed');}
      await loadMasterResumes();
      showToast('✓ Master resume replaced');
    }else{
      const r=await fetch(`${API}/api/memory/master-resumes`,{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({resume}),
      });
      if(!r.ok){const ej=await r.json().catch(()=>({detail:'Upload failed'}));throw new Error(ej.detail||'Upload failed');}
      const created=await r.json();
      _selectedMasterId=created.id;
      await loadMasterResumes();
      showToast(`⭐ Added "${created.name}"`);
    }
  }catch(err){showToast('⚠ '+err.message);}
  e.target.value='';
}

async function setAsMaster(msgId){
  const resume=window[`__r_${msgId}`];
  if(!resume){showToast('⚠ Resume not loaded yet');return;}
  try{
    const r=await fetch(`${API}/api/memory/master-resumes`,{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({resume}),
    });
    if(!r.ok){const ej=await r.json().catch(()=>({detail:'Save failed'}));throw new Error(ej.detail||'Save failed');}
    const created=await r.json();
    _selectedMasterId=created.id;
    await loadMasterResumes();
    showToast(`⭐ Saved as "${created.name}"`);
  }catch(e){showToast('⚠ '+e.message);}
}

async function _saveMasterEdits(edited,silent){
  const sel=_selectedMaster();
  if(!sel){showToast('⚠ No master resume selected');return;}
  try{
    edited.metadata=edited.metadata||{};
    edited.metadata.manually_edited=true;
    edited.metadata.manual_edit_count=(edited.metadata.manual_edit_count||0)+1;
    edited.metadata.last_manually_edited_at=new Date().toISOString();
    const r=await fetch(`${API}/api/memory/master-resumes/${sel.id}`,{
      method:'PUT',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({resume:edited}),
    });
    if(!r.ok){const e=await r.json().catch(()=>({detail:'Save failed'}));throw new Error(e.detail||'Save failed');}
    const updated=await r.json();
    const idx=_masterResumes.findIndex(it=>it.id===sel.id);
    if(idx>=0)_masterResumes[idx]=updated;
    window['__r___master']=JSON.parse(JSON.stringify(updated.resume));
    window['__edit___master']=JSON.parse(JSON.stringify(updated.resume));
    _refreshMsgViewer('__master');
    _updateMasterUI();
    if(!silent)showToast('✓ Master resume saved');
    return {resume_json:updated.resume};
  }catch(e){showToast('⚠️ '+e.message);}
}

// ── Chat "Use Master" dropdown ───────────────────────────────────────────────
// The button lives inside `.hints` (overflow-x:auto), which clips absolutely-
// positioned children. We render the menu into document.body with
// position:fixed and compute its coordinates from the button's rect.
function _ensureMasterAttachMenu(){
  let menu=document.getElementById('master-attach-menu');
  if(!menu){
    menu=document.createElement('div');
    menu.id='master-attach-menu';
    menu.style.cssText='display:none;position:fixed;min-width:240px;max-width:340px;background:var(--bg2);border:1px solid var(--border2);border-radius:9px;box-shadow:var(--shadow-md);padding:4px;z-index:1500;max-height:280px;overflow-y:auto';
    document.body.appendChild(menu);
  }
  return menu;
}

function toggleMasterAttachMenu(ev){
  if(ev)ev.stopPropagation();
  if(_masterResumes.length===0){showToast('No master resumes saved yet');return;}
  if(_masterResumes.length===1){attachMasterById(_masterResumes[0].id);return;}
  const menu=_ensureMasterAttachMenu();
  if(menu.dataset.open==='1'){_hideMasterAttachMenu();return;}
  menu.innerHTML=`<div style="padding:6px 10px;font-size:11px;color:var(--text3);text-transform:uppercase;letter-spacing:.06em">Pick a master resume</div>`+
    _masterResumes.map(it=>`<button class="vm-menu-item" onclick="attachMasterById('${it.id}')" data-id="${it.id}">
      <span style="opacity:${it.is_default?1:0.35}">${it.is_default?'⭐':'☆'}</span>
      <span style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(it.name||'Untitled')}</span>
    </button>`).join('')+
    `<div style="border-top:1px solid var(--bdr);margin:4px 0"></div>
     <button class="vm-menu-item" onclick="closeMasterAttachAndOpenModal()">
       <svg class="ic sm"><use href="#ic-star"/></svg>
       <span style="flex:1">Manage master resumes…</span>
     </button>`;
  // Position above the button if there's room, else below.
  const btn=document.getElementById('master-attach-btn');
  const r=btn.getBoundingClientRect();
  menu.style.visibility='hidden';menu.style.display='block';menu.style.top='0px';menu.style.left='0px';
  const mh=menu.offsetHeight,mw=menu.offsetWidth;
  const spaceAbove=r.top, spaceBelow=window.innerHeight-r.bottom;
  const top=(spaceAbove>=mh+8 || spaceAbove>spaceBelow) ? Math.max(8, r.top-mh-6) : Math.min(window.innerHeight-mh-8, r.bottom+6);
  const left=Math.max(8, Math.min(window.innerWidth-mw-8, r.left));
  menu.style.top=`${top}px`;
  menu.style.left=`${left}px`;
  menu.style.visibility='';
  menu.dataset.open='1';
  document.addEventListener('click',_onMasterMenuClickAway);
}

function _onMasterMenuClickAway(ev){
  const wrap=document.getElementById('master-attach-wrap');
  const menu=document.getElementById('master-attach-menu');
  if(wrap && wrap.contains(ev.target))return;
  if(menu && menu.contains(ev.target))return;
  _hideMasterAttachMenu();
}

function _hideMasterAttachMenu(){
  const menu=document.getElementById('master-attach-menu');
  if(menu){menu.style.display='none';menu.dataset.open='0';}
  document.removeEventListener('click',_onMasterMenuClickAway);
}

function attachMasterById(id){
  _hideMasterAttachMenu();
  const it=_masterResumes.find(x=>x.id===id);
  if(!it){showToast('Master resume not found');return;}
  attachedResume={kind:'json',resume:it.resume,filename:`master_${(it.name||'resume').replace(/\s+/g,'_')}.json`,fromMaster:true};
  document.getElementById('att-ic').innerHTML='<svg class="ic"><use href="#ic-star"/></svg>';
  document.getElementById('att-label').textContent=it.name||'Master Resume';
  document.getElementById('att-meta').textContent='JSON';
  document.getElementById('att-chip').style.display='';
  const btn=document.getElementById('master-attach-btn');
  if(btn)btn.classList.add('on');
  showToast(`⭐ Using "${it.name}"`);
}

function closeMasterAttachAndOpenModal(){
  _hideMasterAttachMenu();
  openMasterModal();
}

// Stable entry points called from sidebar and data-mgmt.
function attachMasterResume(){toggleMasterAttachMenu();}
async function deleteMasterResume(){return deleteSelectedMaster();}
async function loadMasterResume(){return loadMasterResumes();}
