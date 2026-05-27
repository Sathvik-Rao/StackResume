// ── Resume Diff ───────────────────────────────────────────────────────────────
function openDiff(msgId,sessionId){
  const versions=_resumeVersions[sessionId]||[];
  const myIdx=versions.findIndex(v=>v.id===msgId);
  if(myIdx<1)return;
  const prev=versions[myIdx-1].resume;
  const curr=versions[myIdx].resume;
  document.getElementById('diff-ver').textContent=`(v${myIdx} → v${myIdx+1})`;
  document.getElementById('diff-body').innerHTML=_buildDiffHtml(prev,curr);
  document.getElementById('diff-modal').classList.add('open');
}
function closeDiff(){document.getElementById('diff-modal').classList.remove('open');}
document.getElementById('diff-modal').addEventListener('click',e=>{if(e.target===e.currentTarget)closeDiff();});

function _diffWords(a,b){
  if(!a&&!b)return'';
  if(!a)return`<span class="df-add">${esc(b)}</span>`;
  if(!b)return`<span class="df-del">${esc(a)}</span>`;
  if(a===b)return esc(a);
  const aw=a.split(/(\s+)/),bw=b.split(/(\s+)/);
  const m=aw.length,n=bw.length;
  if(m*n>15000)return`<span class="df-del">${esc(a)}</span>\n<span class="df-add">${esc(b)}</span>`;
  const dp=Array.from({length:m+1},()=>new Array(n+1).fill(0));
  for(let i=1;i<=m;i++)for(let j=1;j<=n;j++)
    dp[i][j]=aw[i-1]===bw[j-1]?dp[i-1][j-1]+1:Math.max(dp[i-1][j],dp[i][j-1]);
  const parts=[];let i=m,j=n;
  while(i>0||j>0){
    if(i>0&&j>0&&aw[i-1]===bw[j-1]){parts.unshift({t:'=',v:aw[i-1]});i--;j--;}
    else if(j>0&&(i===0||dp[i][j-1]>=dp[i-1][j])){parts.unshift({t:'+',v:bw[j-1]});j--;}
    else{parts.unshift({t:'-',v:aw[i-1]});i--;}
  }
  return parts.map(p=>p.t==='='?esc(p.v):p.t==='+'?`<span class="df-add">${esc(p.v)}</span>`:`<span class="df-del">${esc(p.v)}</span>`).join('');
}

function _buildDiffHtml(a,b){
  const secs=[];
  const check=(title,va,vb)=>{if(va!==vb)secs.push({title,html:_diffWords(va||'',vb||'')});};

  check('Professional Summary',a.professional_summary,b.professional_summary);

  const ccA=(a.core_competencies||[]).join(', ');
  const ccB=(b.core_competencies||[]).join(', ');
  check('Core Competencies',ccA,ccB);

  const expB=b.experience||[];
  const expA=a.experience||[];
  expB.forEach((job,idx)=>{
    const pj=expA[idx];
    const txtA=pj?[...(pj.responsibilities||[]),...(pj.achievements||[])].join('\n'):'';
    const txtB=[...(job.responsibilities||[]),...(job.achievements||[])].join('\n');
    if(txtA!==txtB)secs.push({title:`Experience — ${job.title} @ ${job.company}`,html:_diffWords(txtA,txtB)});
  });

  const skA=Object.values(a.technical_skills||{}).flat().join(', ');
  const skB=Object.values(b.technical_skills||{}).flat().join(', ');
  check('Technical Skills',skA,skB);

  const metaA=a.metadata||{},metaB=b.metadata||{};
  const scoreKeys=['overall_score','ats_score','quality_score','impact_score'];
  if(scoreKeys.some(k=>metaA[k]!==metaB[k])){
    const scoreHtml=`<div style="display:flex;gap:20px;flex-wrap:wrap">`+
      scoreKeys.map(k=>{
        const va=Math.round(metaA[k]||0),vb=Math.round(metaB[k]||0),d=vb-va;
        const cl=d>0?'df-add':d<0?'df-del':'';
        return`<div style="text-align:center"><div style="font-size:10px;color:var(--text3);margin-bottom:2px">${k.replace('_score','').replace('_',' ').toUpperCase()}</div>`+
          `<div style="font-size:18px;font-weight:700;color:var(--text1)">${vb} <span class="${cl}" style="font-size:11px;font-weight:600">${d>=0?'+':''}${d}</span></div></div>`;
      }).join('')+`</div>`;
    secs.push({title:'Score Changes',html:scoreHtml});
  }

  if(!secs.length)return'<div style="color:var(--text3);font-size:13px;text-align:center;padding:32px 0">No visible changes between these versions.</div>';
  return secs.map(s=>`<div class="diff-section"><div class="diff-section-title">${esc(s.title)}</div><div class="diff-content">${s.html}</div></div>`).join('');
}
