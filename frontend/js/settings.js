// ── Settings ────────────────────────────────────────────────────────────────
// Cache of {provider: model} last selected for each provider. Loaded from the
// server when the cfg-modal opens (so it survives reinstalls / new devices)
// and mirrored to localStorage for instant prefill while the fetch is in flight.
let _modelsByProvider=(function(){try{return JSON.parse(localStorage.getItem('sr_models_by_provider')||'{}')||{};}catch(e){return{};}})();

// openSettings() / closeCfg() now live in section-prefs.js — they route into
// the consolidated #settings-modal and switch to the AI Model tab.
function _relTime(ts){
  if(!ts)return'';
  const s=Math.max(0,Math.round((Date.now()-ts)/1000));
  if(s<60)return s+'s ago';
  if(s<3600)return Math.round(s/60)+'m ago';
  if(s<86400)return Math.round(s/3600)+'h ago';
  return Math.round(s/86400)+'d ago';
}
function rememberTestPrompt(){
  const tp=document.getElementById('llm-test-prompt');
  if(tp)localStorage.setItem('sr_test_prompt',tp.value);
}
function showProvSec(p){
  ['openai','anthropic','google','ollama','custom'].forEach(id=>{
    const el=document.getElementById('sec-'+id);
    if(el)el.style.display=id===p?'':'none';
  });
}
// Copy every saved per-provider model into its input field. Called when the
// modal opens and after the server fetch — so all panes have their value
// ready regardless of which one is currently visible.
function _hydrateAllProviderInputs(){
  ['openai','anthropic','google','ollama','custom'].forEach(id=>{
    const inp=document.getElementById('custom-'+id);
    if(inp&&_modelsByProvider[id])inp.value=_modelsByProvider[id];
  });
}
function _snapshotProviderInputs(){
  ['openai','anthropic','google','ollama','custom'].forEach(id=>{
    const inp=document.getElementById('custom-'+id);
    if(inp&&inp.value.trim())_modelsByProvider[id]=inp.value.trim();
  });
  try{localStorage.setItem('sr_models_by_provider',JSON.stringify(_modelsByProvider));}catch(e){}
}
function updModels(){
  // Capture whatever the user typed across every input before swapping panes,
  // so values aren't lost just because a different provider is now visible.
  _snapshotProviderInputs();
  const p=document.getElementById('prov-sel').value;
  showProvSec(p);
  const cel=document.getElementById('custom-'+p);
  if(cel&&!cel.value&&_modelsByProvider[p])cel.value=_modelsByProvider[p];
}
async function saveCfg(){
  const p=document.getElementById('prov-sel').value;
  const customEl=document.getElementById('custom-'+p);
  let m='';
  if(customEl)m=customEl.value.trim();
  if(!m){showToast('⚠️ Please enter a model name');return;}
  curProv=p;curModel=m;
  // Capture every pane's input value into the map before save, so models
  // typed for other providers in this session aren't lost.
  _snapshotProviderInputs();
  _modelsByProvider[p]=m;
  try{localStorage.setItem('sr_models_by_provider',JSON.stringify(_modelsByProvider));}catch(e){}
  localStorage.setItem('sr_p',p);localStorage.setItem('sr_m',m);
  // Keep the Settings panel open after saving — it only closes via Cancel or ✕.
  updProvPill();showToast('✓ Settings saved — '+p+' / '+m);
  // Collect base URLs from the model tab inputs.
  const _saveBody={models_by_provider:_modelsByProvider};
  const _ollamaUrl=(document.getElementById('model-ollama-url')||{}).value||'';
  const _customUrl=(document.getElementById('model-custom-url')||{}).value||'';
  _saveBody.ollama_base_url=_ollamaUrl.trim();
  _saveBody.openai_base_url=_customUrl.trim();
  // Persist to the backend so settings survive reloads and are shared across devices.
  try{
    const r=await fetch(`${API}/api/app-settings`,{
      method:'PUT',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify(_saveBody)
    });
    if(!r.ok){
      const txt=await r.text();
      showToast('⚠ Saved locally but server rejected: '+txt.slice(0,140));
    }
  }catch(e){
    showToast('⚠ Saved locally — server unreachable');
  }
}
async function testLlmPrompt(){
  const status=document.getElementById('llm-test-status');
  const respBox=document.getElementById('llm-test-response');
  const p=document.getElementById('prov-sel').value;
  const customEl=document.getElementById('custom-'+p);
  const m=customEl?customEl.value.trim():'';
  if(!m){
    status.innerHTML='<span style="color:var(--red)">⚠ Enter a model name first</span>';
    return;
  }
  const prompt=document.getElementById('llm-test-prompt').value.trim()||'Reply with one short sentence.';
  status.textContent='Sending…';
  status.style.color='var(--text3)';
  respBox.style.display='none';
  respBox.textContent='';
  try{
    const r=await fetch(`${API}/api/app-settings/test`,{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({provider:p,model:m,prompt})
    });
    const d=await r.json();
    if(!r.ok)throw new Error(d.detail||'Failed');
    status.innerHTML=`<span style="color:var(--green)">✓ ${esc(p)}/${esc(m)} responded (${d.duration_ms}ms)</span>`;
    respBox.textContent=d.response||'(empty)';
    respBox.style.display='block';
    try{
      localStorage.setItem('sr_test_last',JSON.stringify({
        provider:p,model:m,prompt,response:d.response||'',
        duration_ms:d.duration_ms||null,ts:Date.now()
      }));
    }catch(e){}
  }catch(e){
    status.innerHTML=`<span style="color:var(--red)">⚠ ${esc(e.message)}</span>`;
  }
}

// ── Tabs in settings modals ─────────────────────────────────────────────────
// Scoped to the immediate tab group so nested tab groups (e.g. the API Keys
// sub-tabs inside the consolidated Settings modal) don't leak into the outer
// group's pane visibility.
function swSetTab(scope,btn){
  const target=btn.dataset.pane;
  const tabs=btn.closest('.set-tabs');
  if(!tabs)return;
  tabs.querySelectorAll('.set-tab').forEach(t=>t.classList.toggle('on',t===btn));
  const parent=tabs.parentElement;
  if(!parent)return;
  Array.from(parent.children).forEach(child=>{
    if(child.classList&&child.classList.contains('set-pane')){
      child.classList.toggle('on',child.id===target);
    }
  });
}
function toggleSw(el){el.classList.toggle('on');}
