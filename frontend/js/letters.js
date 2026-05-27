// ── Cover letter & outreach renderers ───────────────────────────────────────
function buildCl(letter,msgId){
  const r=window[`__r_${msgId}`]||{};
  const pi=r.personal_info||{};
  // Capture once so the preview and PDF always show the same date, even if
  // the user clicks PDF after midnight.
  if(!window[`__clDate_${msgId}`])
    window[`__clDate_${msgId}`]=new Date().toLocaleDateString(undefined,{year:'numeric',month:'long',day:'numeric'});
  const today=window[`__clDate_${msgId}`];
  const name=ss(pi.full_name)||'Your Name';
  // Body is pre-normalised on the backend (no salutation, no sign-off, no name)
  // so this preview is byte-for-byte identical to what lands in the PDF.
  const body=(letter||'').trim();
  // Stash so the edit toggle can rebuild without a server round-trip.
  window[`__cl_${msgId}`]=body;
  const bodyHtml=esc(body).replace(/\n\n+/g,'</p><p>').replace(/\n/g,'<br>');

  const contactBits=[];
  ['email','phone','location'].forEach(k=>{const v=ss(pi[k]);if(v)contactBits.push(esc(v));});
  ['linkedin','github','website'].forEach(k=>{const v=ss(pi[k]);if(v)contactBits.push(esc(v.replace(/^https?:\/\//,'').replace(/\/$/,'')));});

  const cid=`cl-${msgId}`;
  return`<div class="cl-wrap" id="${cid}-wrap">
    <div class="cl-bar">
      <button class="ibtn" onclick="cpCl('${msgId}')">${ico('ic-copy')} Copy</button>
      <button class="ibtn" onclick="toggleClEdit('${msgId}')" id="${cid}-edit-btn">${ico('ic-edit-pencil')} Edit</button>
      <button class="ibtn pri" onclick="dlClTxt('${msgId}')">${ico('ic-download')} .txt</button>
      <button class="ibtn pdf" onclick="openClExport('${msgId}')">${ico('ic-download')} Download Cover Letter</button>
    </div>
    <div class="cl-paper" id="${cid}-paper">
      <div class="cl-head">
        <div class="cl-name">${esc(name)}</div>
        ${contactBits.length?`<div class="cl-contact">${contactBits.join(' &nbsp;·&nbsp; ')}</div>`:''}
      </div>
      <div class="cl-rule"></div>
      <div class="cl-date">${esc(today)}</div>
      <div class="cl-salutation">Dear Hiring Team,</div>
      <div class="cl-body" id="${cid}-body"><p>${bodyHtml}</p></div>
      <div class="cl-signoff">Sincerely,</div>
      <div class="cl-sig">${esc(name)}</div>
    </div>
    <div class="cl-edit" id="${cid}-edit" style="display:none">
      <div style="font-size:11.5px;color:var(--text3);margin-bottom:6px">Edit body only — salutation, sign-off, and your name are added automatically.</div>
      <textarea class="fta" id="${cid}-ta" style="min-height:340px;width:100%;font-family:var(--mono);font-size:12.5px;line-height:1.55">${esc(body)}</textarea>
      <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:8px">
        <button class="ibtn" onclick="cancelClEdit('${msgId}')">Cancel</button>
        <button class="ibtn pri" onclick="saveClEdit('${msgId}')">💾 Save edits</button>
      </div>
    </div>
  </div>`;
}

function toggleClEdit(msgId){
  const cid=`cl-${msgId}`;
  const paper=document.getElementById(`${cid}-paper`);
  const edit=document.getElementById(`${cid}-edit`);
  const btn=document.getElementById(`${cid}-edit-btn`);
  if(!paper||!edit)return;
  const editing=edit.style.display!=='none';
  if(editing){
    edit.style.display='none';paper.style.display='';
    if(btn)btn.innerHTML=`${ico('ic-edit-pencil')} Edit`;
  }else{
    edit.style.display='';paper.style.display='none';
    if(btn)btn.innerHTML=`${ico('ic-x')} Close editor`;
    const ta=document.getElementById(`${cid}-ta`);
    if(ta){ta.focus();}
  }
}

function cancelClEdit(msgId){
  const cid=`cl-${msgId}`;
  const ta=document.getElementById(`${cid}-ta`);
  if(ta)ta.value=window[`__cl_${msgId}`]||'';
  toggleClEdit(msgId);
}

async function saveClEdit(msgId){
  const cid=`cl-${msgId}`;
  const ta=document.getElementById(`${cid}-ta`);
  if(!ta)return;
  const body=(ta.value||'').trim();
  try{
    const r=await fetch(`${API}/api/messages/${msgId}/cover-letter`,{
      method:'PATCH',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({cover_letter:body}),
    });
    if(!r.ok){const e=await r.json().catch(()=>({detail:'Save failed'}));throw new Error(e.detail||'Save failed');}
    const m=await r.json();
    window[`__cl_${msgId}`]=m.cover_letter||'';
    // Re-render the cover letter tab so the preview matches the new body.
    const vid=`v${msgId.replace(/-/g,'')}`;
    const host=document.getElementById(`${vid}-cl`);
    if(host)host.innerHTML=buildCl(window[`__cl_${msgId}`],msgId);
    showToast('✓ Cover letter saved');
  }catch(e){showToast('⚠️ '+e.message);}
}
// Copy/download include the full assembled letter so paste into email also has greeting + sign-off
function _fullLetterText(msgId){
  const t=window[`__cl_${msgId}`]||'';
  const r=window[`__r_${msgId}`]||{};
  const name=ss(r?.personal_info?.full_name)||'Your Name';
  return `Dear Hiring Team,\n\n${t.trim()}\n\nSincerely,\n${name}`;
}
function cpCl(msgId){
  if(!window[`__cl_${msgId}`])return;
  navigator.clipboard.writeText(_fullLetterText(msgId));showToast('Cover letter copied');
}
function dlClTxt(msgId){
  if(!window[`__cl_${msgId}`])return;
  const r=window[`__r_${msgId}`];
  const name=(ss(r?.personal_info?.full_name).replace(/\s+/g,'_')||'cover_letter').toLowerCase();
  const b=new Blob([_fullLetterText(msgId)],{type:'text/plain'});
  const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download=`${name}_cover_letter.txt`;a.click();
  showToast('Downloaded');
}
function buildOm(emails,msgId){
  let h='<div class="om-wrap">';
  emails.forEach((em,i)=>{
    const sub=em.subject?`<div class="om-sub"><span class="om-l">Subject</span><span class="om-v">${esc(em.subject)}</span></div>`:'';
    const to=em.to_hint?`<div class="om-sub"><span class="om-l">To</span><span class="om-v">${esc(em.to_hint)}</span></div>`:'';
    const body=esc(em.body||'').replace(/\n/g,'<br>');
    h+=`<div class="om-card">
      <div class="om-head">
        <div class="om-label">${esc(em.label||em.id||'Email '+(i+1))}</div>
        <div class="om-actions">
          <button class="ibtn" onclick="cpOm('${msgId}',${i})">⎘ Copy</button>
          <button class="ibtn pri" onclick="dlOm('${msgId}',${i})">↓ .txt</button>
        </div>
      </div>
      ${to}${sub}
      <div class="om-body">${body}</div>
    </div>`;
  });
  h+='</div>';
  return h;
}
function _omText(em){
  const lines=[];
  if(em.subject)lines.push(`Subject: ${em.subject}`);
  if(em.to_hint)lines.push(`To: ${em.to_hint}`);
  if(lines.length)lines.push('');
  lines.push(em.body||'');
  return lines.join('\n');
}
function cpOm(msgId,i){
  const arr=window[`__om_${msgId}`];if(!arr||!arr[i])return;
  navigator.clipboard.writeText(_omText(arr[i]));showToast('✓ Email copied');
}
function dlOm(msgId,i){
  const arr=window[`__om_${msgId}`];if(!arr||!arr[i])return;
  const em=arr[i];
  const slug=(em.id||'email_'+i).toLowerCase().replace(/[^a-z0-9]+/g,'_');
  const b=new Blob([_omText(em)],{type:'text/plain'});
  const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download=`${slug}.txt`;a.click();
  showToast('✓ Downloaded');
}
