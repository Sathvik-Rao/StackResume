// ── File upload (PDF / JSON / DOCX / TXT) ───────────────────────────────────
let attachedResume=null;     // { kind:'json', resume:{...}, filename } | { kind:'text', text, filename, format }
async function handleFile(ev){
  const file=ev.target.files&&ev.target.files[0];
  ev.target.value='';
  if(!file)return;
  const fd=new FormData();fd.append('file',file);
  showToast('📎 Uploading '+file.name+'…');
  try{
    const r=await fetch(`${API}/api/upload/resume`,{method:'POST',body:fd});
    if(!r.ok){const e=await r.json().catch(()=>({detail:'Upload failed'}));throw new Error(e.detail||'Upload failed');}
    const data=await r.json();
    attachedResume=data;
    const mbtn=document.getElementById('master-attach-btn');
    if(mbtn)mbtn.classList.remove('on');
    const chip=document.getElementById('att-chip');
    document.getElementById('att-label').textContent=data.filename||'resume';
    let meta='';
    if(data.kind==='json'){
      const name=ss(data.resume?.personal_info?.full_name);
      meta=`JSON resume${name?' · '+name:''}`;
    }else{
      meta=`${(data.format||'text').toUpperCase()} · ${data.char_count||0} chars extracted`;
    }
    document.getElementById('att-meta').textContent=meta;
    document.getElementById('att-ic').innerHTML=`<svg class="ic"><use href="#${data.kind==='json'?'ic-doc':'ic-file-text'}"/></svg>`;
    chip.style.display='flex';
    showToast('✓ Attached '+file.name);
  }catch(e){showToast('⚠️ '+e.message);attachedResume=null;}
}
function clearAttachment(){
  attachedResume=null;
  document.getElementById('att-chip').style.display='none';
  const btn=document.getElementById('master-attach-btn');
  if(btn)btn.classList.remove('on');
}
