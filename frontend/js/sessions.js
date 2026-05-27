// ── Sessions ────────────────────────────────────────────────────────────────
const SESSION_LIMIT=25;
let _allSessions=[];
let _sessionHasMore=false;
let _sessionOffset=0;
let _sessionQuery='';       // current server-side search term
let _sessionLoading=false;  // guard against concurrent fetches

async function _fetchSessions(skip,limit,search){
  const q=search?`&search=${encodeURIComponent(search)}`:'';
  const r=await fetch(`${API}/api/sessions?skip=${skip}&limit=${limit}${q}`);
  const data=await r.json();
  return{
    list:Array.isArray(data)?data:(data.sessions||[]),
    hasMore:Array.isArray(data)?false:(data.has_more||false),
  };
}

async function loadSessions(append=false){
  if(_sessionLoading)return;
  _sessionLoading=true;
  const btn=document.querySelector('#sess-load-more button');
  if(btn&&append){btn.disabled=true;btn.textContent='Loading…';}
  const skip=append?_sessionOffset:0;
  try{
    const{list,hasMore}=await _fetchSessions(skip,SESSION_LIMIT,_sessionQuery);
    _allSessions=append?[..._allSessions,...list]:list;
    _sessionOffset=_allSessions.length;
    _sessionHasMore=hasMore;
    renderSList();
  }catch(e){}
  finally{
    _sessionLoading=false;
    if(btn){btn.disabled=false;btn.textContent='Load more';}
  }
}

async function _refreshSessions(){
  // Re-fetch all currently visible sessions (keeps expanded pages intact)
  const count=Math.max(_sessionOffset,SESSION_LIMIT);
  try{
    const{list,hasMore}=await _fetchSessions(0,count,_sessionQuery);
    _allSessions=list;
    _sessionOffset=list.length;
    _sessionHasMore=hasMore;
    renderSList();
  }catch(e){}
}

// Debounced server-side search — resets pagination, fires after 300 ms idle
let _searchTimer=null;
function filterSessions(){
  const val=document.getElementById('sb-search').value;
  document.getElementById('sb-search-clear').style.display=val?'flex':'none';
  clearTimeout(_searchTimer);
  _searchTimer=setTimeout(async()=>{
    _sessionQuery=val.trim();
    _sessionOffset=0;
    _allSessions=[];
    await loadSessions(false);
  },300);
}
function clearSearch(){
  document.getElementById('sb-search').value='';
  filterSessions();
}

function _updateLoadMore(){
  const el=document.getElementById('sess-load-more');
  if(el) el.style.display=_sessionHasMore?'block':'none';
}

function renderSList(){
  const ss=_allSessions;
  const favEl=document.getElementById('sessions-list-fav');
  const histEl=document.getElementById('sessions-list');
  const favHdr=document.getElementById('sl-fav');
  const histHdr=document.getElementById('sl-history');
  const empty=document.getElementById('sessions-empty');
  favEl.innerHTML='';histEl.innerHTML='';
  const favs=ss.filter(s=>s.is_favorite);
  const others=ss.filter(s=>!s.is_favorite);
  favHdr.style.display=favs.length?'block':'none';
  histHdr.style.display=others.length?'block':'none';
  empty.style.display=(!favs.length&&!others.length)?'block':'none';
  empty.textContent=_sessionQuery?'No matches':'No sessions yet';
  const render=(arr,target)=>arr.forEach(s=>{
    const d=document.createElement('div');
    d.className='si'+(s.id===curSession?' on':'')+(s.is_favorite?' fav':'');
    d.dataset.id=s.id;
    const proc=s.is_processing||sessionProcessing[s.id];
    const dotHtml=proc?'<span class="si-running" title="Generating"></span>':'';
    const starIc=s.is_favorite?'ic-star-fill':'ic-star';
    const _SIC={saved:'ic-bookmark',applied:'ic-send',phone_screen:'ic-phone',interviewing:'ic-users',offer:'ic-trophy',rejected:'ic-x-circle',withdrawn:'ic-ban'};
    const badge=s.app_status?`<span class="app-badge ${s.app_status}">${s.app_status.replace('_',' ')}</span>`:'';
    const trkCls=s.has_tracker?' trk-lit':'';
    const statusIc=s.app_status&&_SIC[s.app_status]?_SIC[s.app_status]:'ic-message';
    const leftIcHtml=`<div class="si-ic${trkCls}"><svg class="ic"><use href="#${statusIc}"/></svg></div>`;
    d.innerHTML=`${leftIcHtml}
      <div class="si-info"><div class="si-name" title="${esc(s.title)}">${esc(s.title)}${badge}</div>
        <div class="si-meta">${dotHtml}${relT(s.updated_at)} · ${s.message_count} msgs</div></div>
      <div class="si-act">
        <button class="si-fav-btn ${s.is_favorite?'on':''}" onclick="toggleFav(event,'${s.id}',${!s.is_favorite})" title="${s.is_favorite?'Remove from favorites':'Add to favorites'}"><svg class="ic sm"><use href="#${starIc}"/></svg></button>
        <button class="si-trk" onclick="openTracker(event,'${s.id}')" title="Application tracker" style="background:none;border:none;color:var(--text3);cursor:pointer;padding:3px 4px;border-radius:4px;transition:all .1s;font-size:12px;line-height:1"><svg class="ic sm"><use href="#ic-briefcase"/></svg></button>
        <button class="si-edit" onclick="renameS(event,'${s.id}')" title="Rename"><svg class="ic sm"><use href="#ic-pencil"/></svg></button>
        <button class="si-del" onclick="delS(event,'${s.id}')" title="Delete"><svg class="ic sm"><use href="#ic-trash"/></svg></button>
      </div>`;
    d.addEventListener('click',e=>{if(!e.target.closest('.si-act'))loadSession(s.id)});
    target.appendChild(d);
  });
  render(favs,favEl);render(others,histEl);
  _updateLoadMore();
}
async function toggleFav(e,id,fav){
  e.stopPropagation();
  try{
    await fetch(`${API}/api/sessions/${id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({is_favorite:fav})});
    await _refreshSessions();
  }catch(err){showToast('Failed: '+err.message);}
}
function toggleSidebar(){
  if(window.innerWidth<=700){closeMobileSidebar();return;}
  const sb=document.getElementById('sb');
  const expand=document.getElementById('sb-expand');
  const willCollapse=!sb.classList.contains('collapsed');
  sb.classList.toggle('collapsed',willCollapse);
  expand.style.display=willCollapse?'flex':'none';
  localStorage.setItem('sr_sb_collapsed',willCollapse?'1':'0');
}
function relT(epochMs){
  const d=(Date.now()-epochMs)/1000;
  if(d<60)return'just now';if(d<3600)return`${Math.floor(d/60)}m ago`;
  if(d<86400)return`${Math.floor(d/3600)}h ago`;return`${Math.floor(d/86400)}d ago`;
}

async function newChat(){
  closeMobileSidebar();
  curSession=null;
  document.getElementById('welcome').style.display='';
  document.getElementById('messages').innerHTML='';
  document.getElementById('tb-title').textContent='New Resume';
  syncToolbar();
  document.querySelectorAll('.si').forEach(e=>e.classList.remove('on'));
  // Memory toggle is per-chat; new chats always start with it enabled.
  const mt=document.getElementById('mem-toggle');
  mt.classList.add('on');mt.classList.remove('off');
  document.getElementById('mi').focus();
}

async function loadSession(id){
  closeMobileSidebar();
  curSession=id;
  // Memory toggle resets to on for each chat (per-chat, not global).
  const mt=document.getElementById('mem-toggle');
  mt.classList.add('on');mt.classList.remove('off');
  let session;
  try{
    const r=await fetch(`${API}/api/sessions/${id}`);
    if(!r.ok)return;
    session=await r.json();
  }catch(e){return}
  // Guard: user navigated to a different session while this fetch was in-flight.
  if(curSession!==id)return;
  document.getElementById('tb-title').textContent=session.title;
  document.getElementById('welcome').style.display='none';
  const msgs=document.getElementById('messages');
  msgs.innerHTML='';
  for(const m of session.messages){
    if(m.role==='user'){
      appendUBub(m.content,m.jd_text||null,null,m.created_at);
    }else{
      const c=createARow(m.id);
      messageStates[m.id]={sessionId:id,status:m.status,msg:m,container:c};
      if(m.status==='processing'){
        renderProg(c,m.progress_events||[]);
        sessionProcessing[id]=m.id;
        startPoll(m.id);
      }else if(m.status==='cancelled'){
        renderCancelled(c,m);
      }else if(m.status==='failed'){
        renderError(c,m);
      }else{
        renderDone(c,m);
      }
    }
  }

  // Restore an in-flight send if the server hasn't reflected it yet.
  // Happens when the user submits, then navigates A→B→A faster than the
  // POST can commit to the DB.
  const pending=inFlightSends[id];
  if(pending){
    const userMsgs=session.messages.filter(m=>m.role==='user');
    const lastUser=userMsgs[userMsgs.length-1];
    const matched=lastUser&&lastUser.content===pending.finalContent;
    if(matched){
      // Server already has the user msg — drop the cache so future renders
      // are driven purely by the server's truth.
      delete inFlightSends[id];
    }else{
      appendUBub(pending.content,pending.jdText||null,pending.attachLabel||null,pending.ts);
      const msgId=pending.assistantMessageId;
      if(msgId){
        // POST already resolved during the stale fetch — reuse the live
        // messageStates entry but rebind its container into this view.
        const c=createARow(msgId);
        const st=messageStates[msgId];
        if(st){
          st.container=c;
          renderProg(c,st.msg?.progress_events||[]);
        }else{
          renderProg(c,[{agent:'Intent Guard',status:'running',notes:'Analyzing your request…'}]);
        }
        sessionProcessing[id]=msgId;
        startPoll(msgId);
        pending.container=c;
      }else{
        // POST still in flight — leave a pending row; sendMsg will pick it up.
        const c=createARow('pending');
        renderProg(c,[{agent:'Intent Guard',status:'running',notes:'Analyzing your request…'}]);
        pending.container=c;
      }
    }
  }

  scrollBot();
  document.querySelectorAll('.si').forEach(e=>e.classList.toggle('on',e.dataset.id===id));
  syncToolbar();
}

function renameS(e,id){
  e.stopPropagation();
  const row=document.querySelector(`.si[data-id="${id}"]`);
  if(!row||row.classList.contains('editing'))return;
  const nameEl=row.querySelector('.si-name');
  // Use the title attribute (escaped, badge-free) — `.textContent` would
  // include any app-status badge text that sits inside the same span.
  const oldTitle=nameEl.getAttribute('title')||nameEl.textContent;
  row.classList.add('editing');
  const input=document.createElement('input');
  input.type='text';input.value=oldTitle;input.className='si-rename';
  input.addEventListener('keydown',ev=>{
    if(ev.key==='Enter'){ev.preventDefault();commit();}
    else if(ev.key==='Escape'){ev.preventDefault();cancel();}
  });
  input.addEventListener('blur',commit);
  nameEl.replaceWith(input);input.focus();input.select();
  let done=false;
  async function commit(){
    if(done)return;done=true;
    const v=input.value.trim();
    if(!v||v===oldTitle){cancel();return;}
    try{
      await fetch(`${API}/api/sessions/${id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({title:v})});
      if(curSession===id)document.getElementById('tb-title').textContent=v;
      showToast('✓ Renamed');
    }catch(err){showToast('⚠️ Rename failed');}
    await _refreshSessions();
  }
  function cancel(){if(done)return;done=true;_refreshSessions();}
}

async function delS(e,id){
  e.stopPropagation();
  if(!confirm('Delete session?'))return;
  await fetch(`${API}/api/sessions/${id}`,{method:'DELETE'});
  // Stop any pollers for this session
  Object.entries(messageStates).forEach(([mid,st])=>{
    if(st.sessionId===id){stopPoll(mid);delete messageStates[mid];}
  });
  delete sessionProcessing[id];
  delete inFlightSends[id];
  if(curSession===id){newChat();}
  await _refreshSessions();
}
