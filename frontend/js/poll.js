// ── Poll ────────────────────────────────────────────────────────────────────
function startPoll(msgId){
  if(pollers[msgId])return;
  _scheduleSessionRefreshIfNeeded();
  const doPoll=async()=>{
    try{
      const r=await fetch(`${API}/api/messages/${msgId}/poll`);
      if(!r.ok){stopPoll(msgId);return;}
      const msg=await r.json();
      const st=messageStates[msgId];
      if(!st){stopPoll(msgId);return;}
      st.msg=msg;
      st.status=msg.status;

      // Update UI if container exists
      if(st.container && document.body.contains(st.container)){
        const evts=msg.progress_events||msg.agent_trace||[];
        if(msg.status==='processing'){
          renderProg(st.container,evts);
        }else if(msg.status==='complete'){
          renderDone(st.container,msg);
          scrollBot();
        }else if(msg.status==='cancelled'){
          renderCancelled(st.container,msg);
        }else if(msg.status==='failed'){
          renderError(st.container,msg);
        }
      }

      if(msg.status==='processing'){
        // Update toolbar status text live
        if(st.sessionId===curSession)syncToolbar();
        pollers[msgId]=setTimeout(doPoll,1200);
      }else{
        stopPoll(msgId);
        if(sessionProcessing[st.sessionId]===msgId)delete sessionProcessing[st.sessionId];
        // Drop the in-flight cache once the server has authoritative state.
        if(inFlightSends[st.sessionId]&&inFlightSends[st.sessionId].assistantMessageId===msgId){
          delete inFlightSends[st.sessionId];
        }
        if(st.sessionId===curSession)syncToolbar();
        if(msg.status==='complete'&&msg.resume_json)await _autoTitleSession(st.sessionId,msg.resume_json);
        _refreshSessions();
      }
    }catch(e){pollers[msgId]=setTimeout(doPoll,3000);}
  };
  pollers[msgId]=setTimeout(doPoll,800);
}
function stopPoll(id){if(pollers[id]){clearTimeout(pollers[id]);delete pollers[id];}}
