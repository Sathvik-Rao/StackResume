// ── Send ────────────────────────────────────────────────────────────────────
async function sendMsg(){
  const input=document.getElementById('mi');
  let content=input.value.trim();
  // If current session is generating, ignore (user should stop or open new chat)
  if(curSession && sessionProcessing[curSession])return;

  const jdText=document.getElementById('jd-textarea').value.trim();
  const jdIntensity=jdText?getJdIntensity():null;
  // A JD is by itself a complete instruction — let the user send with an empty
  // prompt and we'll synthesise a sensible default. Without a JD, the prompt
  // text is still required.
  if(!content){
    if(jdText)content='Tailor my resume to this job description.';
    else return;
  }

  let sessionId=curSession;
  if(!sessionId){
    try{
      const r=await fetch(`${API}/api/sessions`,{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({title:'New Resume',llm_provider:curProv,llm_model:curModel})});
      sessionId=(await r.json()).id;
    }catch(err){
      // Restore the prompt so the user can retry.
      input.value=content;autoResize();
      showToast('⚠️ '+(err.message||'Failed to create session'));
      return;
    }
    // Only adopt as current session if the user hasn't navigated during await.
    // Otherwise the send still goes through under the new session, but we
    // don't yank the user's view away from where they navigated to.
    if(curSession===null)curSession=sessionId;
  }

  // Stitch any attached PDF/text resume into the user prompt.
  // JSON resumes flow via the structured `attached_resume` field instead.
  let finalContent=content;
  let attachedJson=null;
  let attachLabel=null;
  let fromMasterName=null;
  if(attachedResume){
    if(attachedResume.kind==='json'&&attachedResume.resume){
      attachedJson=attachedResume.resume;
      attachLabel=`JSON · ${attachedResume.filename||'resume.json'}`;
      if(attachedResume.fromMaster)fromMasterName=attachedResume.masterName||'Master Resume';
    }else if(attachedResume.kind==='text'&&attachedResume.text){
      const trimmed=attachedResume.text.length>14000?attachedResume.text.slice(0,14000)+'\n…[truncated]':attachedResume.text;
      finalContent=`[ATTACHED RESUME — extracted from ${attachedResume.filename||'upload'}]\n${trimmed}\n[END ATTACHED RESUME]\n\n${content}`;
      attachLabel=`${(attachedResume.format||'text').toUpperCase()} · ${attachedResume.filename||''}`;
    }
  }

  const sendTs=Date.now();
  // Cache the in-flight send so loadSession can restore the user bubble and
  // pending row if the user navigates away and back before the POST commits.
  inFlightSends[sessionId]={content,jdText,attachLabel,finalContent,ts:sendTs};

  input.value='';autoResize();

  // Only paint into the current view if the user is still on this session.
  let tempC=null;
  if(curSession===sessionId){
    document.getElementById('welcome').style.display='none';
    appendUBub(content,jdText,attachLabel,sendTs);
    tempC=createARow('pending');
    renderProg(tempC,[{agent:'Intent Guard',status:'running',notes:'Analyzing your request…'}]);
  }

  // Snapshot then clear the attachment for the next message
  const submitAttached=attachedJson;
  clearAttachment();
  if(jdText)closeJD();

  try{
    const r=await fetch(`${API}/api/sessions/${sessionId}/messages`,{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({content:finalContent,jd_text:jdText||null,jd_intensity:jdIntensity,attached_resume:submitAttached,from_master_name:fromMasterName,use_memory:isMemoryOn(),llm_provider:curProv,llm_model:curModel})});
    if(!r.ok)throw new Error(`HTTP ${r.status}`);
    const d=await r.json();

    // If loadSession ran while the POST was in flight, it may have installed
    // its own pending container in inFlightSends. Prefer that one; otherwise
    // fall back to the original tempC (if still attached). If neither is in
    // the DOM and we're on this session, create a fresh row now.
    const pending=inFlightSends[sessionId];
    let container=null;
    if(pending&&pending.container&&document.body.contains(pending.container)){
      container=pending.container;
    }else if(tempC&&document.body.contains(tempC)){
      container=tempC;
    }else if(curSession===sessionId){
      container=createARow(d.assistant_message_id);
      renderProg(container,[{agent:'Intent Guard',status:'running',notes:'Analyzing your request…'}]);
      scrollBot();
    }
    if(container)container.dataset.msgId=d.assistant_message_id;

    messageStates[d.assistant_message_id]={sessionId,status:'processing',msg:{progress_events:[]},container};
    sessionProcessing[sessionId]=d.assistant_message_id;

    // Remember the asst msg id on the in-flight entry so loadSession can
    // reconnect via messageStates instead of creating a fresh pending row.
    if(pending)pending.assistantMessageId=d.assistant_message_id;

    if(curSession===sessionId)syncToolbar();
    startPoll(d.assistant_message_id);
    await _refreshSessions();
  }catch(err){
    delete inFlightSends[sessionId];
    const fail=(tempC&&document.body.contains(tempC))?tempC:null;
    if(fail)fail.innerHTML=`<div class="at" style="color:var(--red)">⚠️ ${esc(err.message)}</div>`;
    else if(curSession===sessionId)showToast('⚠️ '+err.message);
  }
}

async function stopGen(){
  const msgId=curSession?sessionProcessing[curSession]:null;
  if(!msgId)return;
  try{
    await fetch(`${API}/api/messages/${msgId}/cancel`,{method:'POST'});
  }catch(e){}
  // Poller will pick up the new status
}
