// ── API Keys & Environment ───────────────────────────────────────────────────
// openKeys() / closeKeys() now live in section-prefs.js — they route into the
// consolidated #settings-modal and switch to the API Keys tab.
async function refreshKeysModal(){
  try{
    const r=await fetch(`${API}/api/app-settings`);
    if(!r.ok)return;
    const s=await r.json();
    const set=s._secrets_set||{};
    const flag=(id,key)=>{
      const el=document.getElementById(id);
      if(set[key]){el.className='key-status set';el.textContent='set';}
      else{el.className='key-status unset';el.textContent='not set';}
    };
    flag('ks-openai','openai_api_key');
    flag('ks-anthropic','anthropic_api_key');
    flag('ks-google','google_api_key');
    flag('ks-langsmith','langsmith_api_key');
    document.getElementById('k-openai').value='';
    document.getElementById('k-anthropic').value='';
    document.getElementById('k-google').value='';
    document.getElementById('k-ls-key').value='';
    document.getElementById('k-ls-project').value=s.langsmith_project||'';
    document.getElementById('k-ls-toggle').classList.toggle('on',!!s.langsmith_tracing);
    document.getElementById('k-iters').value=s.max_review_iterations||'';
    document.getElementById('k-minscore').value=s.min_quality_score||'';
    document.getElementById('k-temp').value=(s.llm_temperature!==null&&s.llm_temperature!==undefined)?s.llm_temperature:'';
  }catch(e){}
}
async function saveKeys(){
  try{
    const r=await fetch(`${API}/api/app-settings`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(_collectKeysBody())});
    if(!r.ok)throw new Error(await r.text());
    showToast('Settings saved');
    closeSettingsModal();
  }catch(e){showToast('Save failed: '+e.message);}
}
async function testLangsmith(){
  const status=document.getElementById('ls-test-status');
  status.textContent='Saving + testing…';
  status.style.color='var(--text3)';
  // Save current settings first so the test uses what's in the form
  await saveKeysSilent();
  try{
    // Send the user's *active* provider/model — the prov pill comes from localStorage,
    // not AppSettings, so the server doesn't know it otherwise.
    const r=await fetch(`${API}/api/app-settings/test-langsmith`,{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({provider:curProv,model:curModel})
    });
    const d=await r.json();
    if(!r.ok)throw new Error(d.detail||'Failed');
    status.innerHTML=`<span style="color:var(--green)">✓ Trace sent to ${esc(d.project)} · ${esc(d.provider)}/${esc(d.model)} (${d.duration_ms}ms)</span>`;
  }catch(e){
    status.innerHTML=`<span style="color:var(--red)">⚠ ${esc(e.message)}</span>`;
  }
}
async function saveKeysSilent(){
  const body=_collectKeysBody();
  await fetch(`${API}/api/app-settings`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
}
function _collectKeysBody(){
  const body={};
  const sv=(id,k)=>{const v=document.getElementById(id).value.trim();if(v)body[k]=v;};
  sv('k-openai','openai_api_key');
  sv('k-anthropic','anthropic_api_key');
  sv('k-google','google_api_key');
  sv('k-ls-key','langsmith_api_key');
  body.langsmith_project=document.getElementById('k-ls-project').value.trim();
  body.langsmith_tracing=document.getElementById('k-ls-toggle').classList.contains('on');
  const it=document.getElementById('k-iters').value;if(it)body.max_review_iterations=parseInt(it);
  const ms=document.getElementById('k-minscore').value;if(ms)body.min_quality_score=parseFloat(ms);
  const tp=document.getElementById('k-temp').value;if(tp!=='')body.llm_temperature=parseFloat(tp);
  return body;
}
async function resetKeys(){
  if(!confirm('Reset all overrides — fall back to .env values?'))return;
  try{
    await fetch(`${API}/api/app-settings`,{method:'DELETE'});
    showToast('✓ Reset to .env');
    await refreshKeysModal();
  }catch(e){showToast('⚠️ '+e.message);}
}
