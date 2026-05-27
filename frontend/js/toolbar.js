// ── Toolbar / send-button state sync ────────────────────────────────────────
function syncToolbar(){
  const procMsgId=curSession?sessionProcessing[curSession]:null;
  const isGen=!!procMsgId;
  document.getElementById('sb-btn').style.display=isGen?'none':'flex';
  document.getElementById('stop-btn').classList.toggle('show',isGen);
  document.getElementById('tb-status').classList.toggle('show',isGen);
  if(isGen){
    const st=messageStates[procMsgId];
    const evts=st?.msg?.progress_events||st?.msg?.agent_trace||[];
    const running=evts.find(e=>e.status==='running');
    document.getElementById('tb-status-txt').textContent=running?running.agent:'Generating…';
  }
}
