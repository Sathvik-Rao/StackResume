// ── Application Tracker ───────────────────────────────────────────────────────
function openTracker(e,id){
  e.stopPropagation();
  document.getElementById('tracker-sid').value=id;
  // Load full session data for tracker fields
  fetch(`${API}/api/sessions/${id}`).then(r=>r.json()).then(s=>{
    _setStatBtn(s.app_status||'');
    document.getElementById('tracker-url').value=s.apply_url||'';
    document.getElementById('tracker-account').value=s.apply_account||'';
    document.getElementById('tracker-password').value=s.apply_password||'';
    document.getElementById('tracker-password').type='password';
    document.getElementById('tracker-pw-eye').textContent='Show';
    document.getElementById('tracker-notes').value=s.notes||'';
    toggleApplyOpen();
    document.getElementById('tracker-modal').classList.add('open');
  });
}
function closeTracker(){document.getElementById('tracker-modal').classList.remove('open');}
function pickStatus(btn){_setStatBtn(btn.dataset.val);}
function _setStatBtn(val){
  document.querySelectorAll('.stat-btn').forEach(b=>{
    b.classList.toggle('on',b.dataset.val===val);
  });
}
function toggleTrackerPw(){
  const inp=document.getElementById('tracker-password');
  const btn=document.getElementById('tracker-pw-eye');
  inp.type=inp.type==='password'?'text':'password';
  btn.textContent=inp.type==='password'?'Show':'Hide';
}
function toggleApplyOpen(){
  const url=document.getElementById('tracker-url').value.trim();
  document.getElementById('tracker-url-open').style.display=url?'':'none';
}
function openApplyUrl(){
  const url=document.getElementById('tracker-url').value.trim();
  if(url)window.open(url,'_blank','noopener');
}
async function saveTracker(){
  const id=document.getElementById('tracker-sid').value;
  const status=document.querySelector('.stat-btn.on')?.dataset.val||'';
  const body={
    app_status:status||'',
    apply_url:document.getElementById('tracker-url').value.trim(),
    apply_account:document.getElementById('tracker-account').value.trim(),
    apply_password:document.getElementById('tracker-password').value,
    notes:document.getElementById('tracker-notes').value.trim(),
  };
  await fetch(`${API}/api/sessions/${id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  closeTracker();
  await _refreshSessions();
  showToast('✓ Application info saved');
}
document.getElementById('tracker-modal').addEventListener('click',e=>{if(e.target===e.currentTarget)closeTracker();});
