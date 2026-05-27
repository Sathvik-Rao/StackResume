// ── Data Management ──────────────────────────────────────────────────────────
// openDataMgmt() / closeSettingsModal() now live in section-prefs.js — they route
// into the consolidated #settings-modal and switch to the Data Management tab.

async function deleteNonFavChats(){
  if(!confirm('Delete all non-favorite chats? Starred sessions will be kept.'))return;
  const r=await fetch(`${API}/api/sessions?keep_favorites=true`,{method:'DELETE'});
  const d=await r.json();
  Object.entries(messageStates).forEach(([mid,st])=>{if(!sessionProcessing[st?.sessionId])return;stopPoll(mid);delete messageStates[mid];});
  if(curSession&&!sessionProcessing[curSession])newChat();
  await _refreshSessions();
  closeSettingsModal();
  showToast(`✓ Deleted ${d.deleted} chat${d.deleted!==1?'s':''}`);
}

async function deleteAllChats(){
  if(!confirm('Delete ALL chats? This cannot be undone.'))return;
  const r=await fetch(`${API}/api/sessions`,{method:'DELETE'});
  const d=await r.json();
  Object.keys(messageStates).forEach(mid=>stopPoll(mid));
  Object.keys(messageStates).forEach(k=>delete messageStates[k]);
  Object.keys(sessionProcessing).forEach(k=>delete sessionProcessing[k]);
  Object.keys(inFlightSends).forEach(k=>delete inFlightSends[k]);
  newChat();
  await _refreshSessions();
  closeSettingsModal();
  showToast(`✓ Deleted ${d.deleted} chat${d.deleted!==1?'s':''}`);
}

async function resetMetrics(){
  if(!confirm('Reset all metrics data? Token counts, scores and agent traces will be cleared.'))return;
  await fetch(`${API}/api/metrics`,{method:'DELETE'});
  closeSettingsModal();
  showToast('✓ Metrics reset');
}

async function clearMemoryFromDataMgmt(){
  if(!confirm('Clear all saved profile data?'))return;
  await fetch(`${API}/api/memory`,{method:'DELETE'});
  await loadMemoryChip();
  closeSettingsModal();
  showToast('✓ Profile memory cleared');
}
