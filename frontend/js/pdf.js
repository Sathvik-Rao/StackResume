// ── PDF ─────────────────────────────────────────────────────────────────────
function selTmpl(card){
  document.querySelectorAll('.tmpl-card').forEach(c=>c.classList.remove('sel'));
  card.classList.add('sel');pdfTemplate=card.dataset.tmpl;
  schedulePreviewUpdate();
}
const FMT_HINTS={
  pdf:'PDF — universal, print-ready, recommended for online job portals.',
  docx:'Word .docx — editable in Microsoft Word, Google Docs, Pages.',
  odt:'OpenDocument .odt — editable in LibreOffice / OpenOffice.',
};
const _FS_PRESET_PT={small:9.5,normal:10.5,large:11.5};
const _FS_MIN=8.0,_FS_MAX=13.0;

// Sync slider, number input, and preset chips for a given pt value, then
// update `pdfFs` (preset name if it matches one, else numeric string) and
// schedule a preview refresh.
function _applyFs(pt,{skipSlider=false,skipNum=false}={}){
  pt=Math.max(_FS_MIN, Math.min(_FS_MAX, pt));
  const slider=document.getElementById('fs-slider');
  const num=document.getElementById('fs-num');
  if(slider && !skipSlider)slider.value=String(Math.round(pt*10));
  if(num && !skipNum){
    const want=pt.toFixed(1);
    if(num.value!==want)num.value=want;
  }
  const matched=Object.entries(_FS_PRESET_PT).find(([,v])=>Math.abs(v-pt)<0.05);
  document.querySelectorAll('.opt-btn[data-fs]').forEach(b=>{
    b.classList.toggle('sel', !!(matched && b.dataset.fs===matched[0]));
  });
  pdfFs = matched ? matched[0] : pt.toFixed(1);
  schedulePreviewUpdate();
}

function selOpt(type,btn){
  const parent=btn.closest('.opt-row');
  parent.querySelectorAll('.opt-btn').forEach(b=>b.classList.remove('sel'));
  btn.classList.add('sel');
  if(type==='fs'){
    const pt=_FS_PRESET_PT[btn.dataset.fs];
    if(pt!==undefined){_applyFs(pt);}
    return; // _applyFs already scheduled the preview
  }
  if(type==='mp')pdfMp=btn.dataset.mp;
  else if(type==='fmt'){
    pdfFmt=btn.dataset.fmt;
    const hint=document.getElementById('fmt-hint');if(hint)hint.textContent=FMT_HINTS[pdfFmt]||'';
  }
  schedulePreviewUpdate();
}

function onFsSlider(el){
  _applyFs(parseInt(el.value,10)/10, {skipSlider:true});
}
function onFsNum(el){
  const pt=parseFloat(el.value);
  if(isNaN(pt))return; // user is mid-edit (e.g. just typed "."); wait
  // Don't echo back into the input mid-typing — only sync slider + chips.
  _applyFs(pt, {skipNum:true});
}
function closePdf(){
  document.getElementById('pdf-modal').classList.remove('open');
  // Free any blob URL we were holding so we don't leak memory across opens.
  const frame=document.getElementById('exp-prev-frame');
  if(frame && frame.dataset.blobUrl){
    try{URL.revokeObjectURL(frame.dataset.blobUrl);}catch{}
    frame.dataset.blobUrl='';frame.src='about:blank';
  }
  if(_pdfFromMaster){
    _pdfFromMaster=false;
    openMasterModal();
  }
}

// Debounce successive option clicks so we don't fire a request per keystroke.
let _previewTimer=null;
let _previewReq=0;
function schedulePreviewUpdate(){
  if(!document.getElementById('pdf-modal').classList.contains('open'))return;
  clearTimeout(_previewTimer);
  _previewTimer=setTimeout(updateExportPreview,180);
}
function refreshExportPreview(){updateExportPreview();}

async function updateExportPreview(){
  const frame=document.getElementById('exp-prev-frame');
  const empty=document.getElementById('exp-prev-empty');
  const label=document.getElementById('exp-prev-label');
  if(!pdfResume){
    frame.style.display='none';
    empty.textContent='No resume selected.';
    empty.style.display='flex';
    return;
  }
  // Cover letters and PDF resumes both render fine; non-PDF formats can't be inlined.
  if(pdfFmt!=='pdf'){
    frame.style.display='none';
    empty.innerHTML='Inline preview is only available for PDF.<br><span style="font-size:11px;color:var(--text3)">The selected template will be applied to the downloaded '+pdfFmt.toUpperCase()+' file.</span>';
    empty.style.display='flex';
    label.textContent=`Preview — ${_tmplLabel(pdfTemplate)} (${pdfFmt.toUpperCase()})`;
    return;
  }
  const myReq=++_previewReq;
  empty.textContent='Building preview…';
  empty.style.display='flex';
  frame.style.display='none';
  label.textContent=`Preview — ${_tmplLabel(pdfTemplate)}`;
  try{
    let resp;
    if(exportKind==='coverletter'){
      const t=exportClMsgId?window[`__cl_${exportClMsgId}`]:null;
      if(!t){throw new Error('No cover letter');}
      const clientDate=(exportClMsgId && window[`__clDate_${exportClMsgId}`])||new Date().toLocaleDateString(undefined,{year:'numeric',month:'long',day:'numeric'});
      resp=await fetch(`${API}/api/documents/cover-letter`,{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({cover_letter:t,resume_json:pdfResume,template:pdfTemplate,font_size:pdfFs,date:clientDate,format:'pdf',inline:true}),
      });
    }else{
      resp=await fetch(`${API}/api/documents/generate`,{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({resume_json:pdfResume,template:pdfTemplate,font_size:pdfFs,max_pages:pdfMp,format:'pdf',inline:true}),
      });
    }
    if(!resp.ok){throw new Error('Preview failed');}
    const blob=await resp.blob();
    // Ignore stale responses if a newer request kicked off while this was in-flight.
    if(myReq!==_previewReq){return;}
    if(frame.dataset.blobUrl){try{URL.revokeObjectURL(frame.dataset.blobUrl);}catch{}}
    const url=URL.createObjectURL(blob);
    frame.dataset.blobUrl=url;
    frame.src=url+'#toolbar=0&navpanes=0&zoom=page-width';
    frame.style.display='block';
    empty.style.display='none';
  }catch(e){
    if(myReq!==_previewReq)return;
    empty.textContent='⚠️ Could not build preview. Download will still work.';
    empty.style.display='flex';
  }
}
function _tmplLabel(t){return {classic_ats:'Classic ATS',modern_clean:'Modern Clean',executive_dark:'Executive',dark_theme:'Dark Theme'}[t]||t;}

async function downloadDoc(){
  if(exportKind==='coverletter'){return downloadCoverLetter();}
  return downloadResume();
}

async function downloadResume(){
  if(!pdfResume){showToast('No resume to export');return;}
  const btn=document.getElementById('pdf-dl-btn');
  btn.textContent='Generating…';btn.disabled=true;
  try{
    const r=await fetch(`${API}/api/documents/generate`,{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({resume_json:pdfResume,template:pdfTemplate,font_size:pdfFs,max_pages:pdfMp,format:pdfFmt})
    });
    if(!r.ok){const e=await r.json().catch(()=>({detail:'Export failed'}));throw new Error(e.detail||'Export failed');}
    const blob=await r.blob();
    const name=(ss(pdfResume?.personal_info?.full_name).replace(/\s+/g,'_')||'resume').toLowerCase();
    const url=URL.createObjectURL(blob);
    const a=document.createElement('a');a.href=url;a.download=`${name}_${pdfTemplate}.${pdfFmt}`;a.click();
    setTimeout(()=>{try{URL.revokeObjectURL(url);}catch{}},1000);
    closePdf();showToast(`✓ ${pdfFmt.toUpperCase()} downloaded`);
  }catch(e){showToast('⚠️ '+e.message);}
  finally{btn.textContent='⬇ Download';btn.disabled=false;}
}

async function downloadCoverLetter(){
  const t=exportClMsgId?window[`__cl_${exportClMsgId}`]:null;
  if(!t){showToast('No cover letter to export');return;}
  const r=window[`__r_${exportClMsgId}`]||pdfResume;
  const clientDate=window[`__clDate_${exportClMsgId}`]||new Date().toLocaleDateString(undefined,{year:'numeric',month:'long',day:'numeric'});
  const btn=document.getElementById('pdf-dl-btn');
  btn.textContent='Generating…';btn.disabled=true;
  try{
    const resp=await fetch(`${API}/api/documents/cover-letter`,{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({cover_letter:t,resume_json:r,template:pdfTemplate,font_size:pdfFs,date:clientDate,format:pdfFmt}),
    });
    if(!resp.ok){const e=await resp.json().catch(()=>({detail:'Export failed'}));throw new Error(e.detail||'Export failed');}
    const blob=await resp.blob();
    const name=(ss(r?.personal_info?.full_name).replace(/\s+/g,'_')||'cover_letter').toLowerCase();
    const url=URL.createObjectURL(blob);
    const a=document.createElement('a');a.href=url;a.download=`${name}_cover_letter.${pdfFmt}`;a.click();
    setTimeout(()=>{try{URL.revokeObjectURL(url);}catch{}},1000);
    closePdf();showToast(`✓ Cover letter ${pdfFmt.toUpperCase()} downloaded`);
  }catch(e){showToast('⚠️ '+e.message);}
  finally{btn.textContent='⬇ Download';btn.disabled=false;}
}
document.getElementById('pdf-modal').addEventListener('click',e=>{if(e.target===e.currentTarget)closePdf()});
document.getElementById('logout-modal').addEventListener('click',e=>{if(e.target===e.currentTarget)cancelLogout()});
