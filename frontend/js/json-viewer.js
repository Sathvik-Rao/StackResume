// ── JSON viewer ──────────────────────────────────────────────────────────────
function buildViewer(resume,msgId,coverLetter,outreach){
  const vid=`v${msgId.replace(/-/g,'')}`;
  const hasCover=!!coverLetter;
  const hasOutreach=outreach&&outreach.length;
  // Stash for use by tab handlers
  if(hasCover)window[`__cl_${msgId}`]=coverLetter;
  if(hasOutreach)window[`__om_${msgId}`]=outreach;

  const tabs=[
    `<button class="jtab on" data-tab="pv" onclick="swTab('${vid}','pv',this)">${ico('ic-doc')} Preview</button>`,
    `<button class="jtab" data-tab="edit" onclick="swTab('${vid}','edit',this);renderEditor('${msgId}')">${ico('ic-edit-pencil')} Edit</button>`,
    `<button class="jtab" data-tab="raw" onclick="swTab('${vid}','raw',this)">{ } JSON</button>`,
  ];
  if(hasCover)tabs.push(`<button class="jtab" data-tab="cl" onclick="swTab('${vid}','cl',this)">${ico('ic-mail')} Cover Letter</button>`);
  if(hasOutreach)tabs.push(`<button class="jtab" data-tab="om" onclick="swTab('${vid}','om',this)">${ico('ic-mail')} Outreach (${outreach.length})</button>`);

  const editedBadge=(resume?.metadata?.manually_edited)
    ? `<span class="ed-badge" title="This resume has been manually edited">${ico('ic-edit-pencil')} Edited</span>`
    : '';

  return`<div class="jv-tb">
      <div class="jv-l">
        <div class="jv-title">Result</div>
        ${editedBadge}
        <div class="tabs">${tabs.join('')}</div>
      </div>
      <div class="jv-r">
        <button class="ibtn" onclick="setAsMaster('${msgId}')" title="Save this resume as your master template">${ico('ic-star')} Set as Master</button>
        <button class="ibtn" onclick="cpR('${msgId}')">${ico('ic-copy')} Copy JSON</button>
        <button class="ibtn pri" onclick="dlJson('${msgId}')">${ico('ic-download')} JSON</button>
        <button class="ibtn pdf" onclick="openPdf('${msgId}')">${ico('ic-download')} Download Resume</button>
      </div>
    </div>
    <div class="jvb" id="${vid}-pv">${buildPv(resume)}</div>
    <div class="jvb" id="${vid}-edit" style="display:none"><div id="${vid}-edit-body"></div></div>
    <div class="jvb" id="${vid}-raw" style="display:none"><pre class="jp">${synHl(resume)}</pre></div>
    ${hasCover?`<div class="jvb" id="${vid}-cl" style="display:none">${buildCl(coverLetter,msgId)}</div>`:''}
    ${hasOutreach?`<div class="jvb" id="${vid}-om" style="display:none">${buildOm(outreach,msgId)}</div>`:''}`;
}

function swTab(vid,tab,btn){
  ['pv','edit','raw','cl','om'].forEach(t=>{
    const el=document.getElementById(`${vid}-${t}`);
    if(el)el.style.display=t===tab?'':'none';
  });
  btn.closest('.tabs').querySelectorAll('.jtab').forEach(t=>t.classList.remove('on'));
  btn.classList.add('on');
}
function cpR(msgId){
  const r=window[`__r_${msgId}`];if(!r)return;
  navigator.clipboard.writeText(JSON.stringify(r,null,2));showToast('✓ Copied to clipboard');
}
function dlJson(msgId){
  const r=window[`__r_${msgId}`];if(!r)return;
  const name=ss(r?.personal_info?.full_name).replace(/\s+/g,'_').toLowerCase()||'resume';
  const b=new Blob([JSON.stringify(r,null,2)],{type:'application/json'});
  const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download=`${name}_resume.json`;a.click();
  showToast('✓ Downloaded JSON');
}
function openPdf(msgId){
  const r=window[`__r_${msgId}`];if(!r)return;
  pdfResume=r;
  exportKind='resume';exportClMsgId=null;
  _pdfFromMaster=false;
  document.getElementById('export-title').textContent='📄 Export Resume';
  document.getElementById('pages-fg').style.display='';
  document.getElementById('pdf-modal').classList.add('open');
  updateExportPreview();
}
