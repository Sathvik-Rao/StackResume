// ── Init ────────────────────────────────────────────────────────────────────
// ── Theme controller ────────────────────────────────────────────────────────
function _resolvedTheme(pref){
  return pref==='system'
    ?(window.matchMedia('(prefers-color-scheme: light)').matches?'light':'dark')
    :pref;
}
function _applyTheme(pref){
  document.documentElement.setAttribute('data-theme',_resolvedTheme(pref));
}
function _updateThemeUI(pref){
  document.querySelectorAll('.theme-toggle button').forEach(b=>{
    b.classList.toggle('on',b.dataset.th===pref);
  });
}
function setTheme(pref){
  if(!['system','light','dark'].includes(pref))pref='system';
  localStorage.setItem('sr_theme',pref);
  _applyTheme(pref);
  _updateThemeUI(pref);
}
function _initTheme(){
  const pref=localStorage.getItem('sr_theme')||'system';
  _applyTheme(pref);
  _updateThemeUI(pref);
  // Follow OS changes while in "system" mode
  const mq=window.matchMedia('(prefers-color-scheme: light)');
  const onChange=()=>{
    if((localStorage.getItem('sr_theme')||'system')==='system')_applyTheme('system');
  };
  if(mq.addEventListener)mq.addEventListener('change',onChange);
  else if(mq.addListener)mq.addListener(onChange);
}

async function init(){
  _initTheme();
  // Restore collapsed sidebar state
  if(localStorage.getItem('sr_sb_collapsed')==='1'){
    document.getElementById('sb').classList.add('collapsed');
    document.getElementById('sb-expand').style.display='flex';
  }
  // Pull live server defaults so the pill shows what'll actually run
  await loadServerDefaults();
  loadJdIntensityDefault();
  updProvPill();
  await loadSessions();
  await loadMemoryChip();
  await loadMasterResumes();
  autoResize();
  await adoptInflightFromServer();
}

// Only refreshes session list while messages are actively being polled.
// Self-terminates when all polls finish; re-triggered by startPoll().
let _sessionRefreshPending=false;
function _scheduleSessionRefreshIfNeeded(){
  if(_sessionRefreshPending||Object.keys(pollers).length===0)return;
  _sessionRefreshPending=true;
  setTimeout(async()=>{
    _sessionRefreshPending=false;
    await _refreshSessions();
    _scheduleSessionRefreshIfNeeded();
  },10000);
}

async function loadServerDefaults(){
  // Only override localStorage if user hasn't picked anything yet
  if(localStorage.getItem('sr_p')&&localStorage.getItem('sr_m'))return;
  try{
    const r=await fetch(`${API}/api/app-settings`);
    if(!r.ok)return;
    const s=await r.json();
    if(s.llm_provider)curProv=s.llm_provider;
    if(s.llm_model)curModel=s.llm_model;
  }catch(e){}
}

async function loadJdIntensityDefault(){
  try{
    const r=await fetch(`${API}/api/app-settings`);
    if(!r.ok)return;
    const s=await r.json();
    if(s.default_jd_intensity==null)return;
    const v=Math.max(0,Math.min(100,parseInt(s.default_jd_intensity,10)));
    if(isNaN(v))return;
    const sl=document.getElementById('jd-intensity');
    if(sl){sl.value=v;updateJdIntensityUI();}
  }catch(e){}
}

async function adoptInflightFromServer(){
  try{
    for(const s of _allSessions){
      if(!s.is_processing) continue;
      const sr=await fetch(`${API}/api/sessions/${s.id}`);
      const session=await sr.json();
      for(const m of session.messages){
        if(m.role==='assistant'&&m.status==='processing'){
          messageStates[m.id]={sessionId:s.id,status:m.status,msg:m,container:null};
          sessionProcessing[s.id]=m.id;
          startPoll(m.id);
        }
      }
    }
  }catch(e){}
}

function updProvPill(){document.getElementById('prov-lbl').textContent=`${curProv} / ${curModel}`}
