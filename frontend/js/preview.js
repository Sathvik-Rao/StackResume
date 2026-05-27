// ── Preview (full, every section) ───────────────────────────────────────────
function ss(v){
  if(v===null||v===undefined)return'';
  if(typeof v==='string')return v;
  if(typeof v==='number'||typeof v==='boolean')return String(v);
  if(Array.isArray(v))return v.map(ss).filter(Boolean).join(', ');
  if(typeof v==='object'){
    // handle LLM variants: {action,result} or {metric} emitted by local models
    const parts=[v.action||'',v.result||'',v.metric||''].map(s=>String(s).trim()).filter(Boolean);
    if(parts.length)return parts.join(' ');
    return v.name||v.title||v.value||v.text||v.description||'';
  }
  return String(v);
}
// Coerce LLM-emitted fields into arrays. Many "list" fields (activities,
// interests, technologies, coursework, etc.) come back as a single
// comma-separated string instead of a list. Treating a string as an array
// also accidentally spreads it into chars elsewhere, so normalize early.
// Also undoes the upstream `list(some_string)` damage where a string was
// coerced into ["A","c","t","i","v","i","t","i","e","s",":",";"...].
function toArr(v){
  if(v===null||v===undefined)return[];
  if(Array.isArray(v)){
    // If most entries are single chars, the upstream pipeline almost certainly
    // ran `list(<string>)` on a sentence — rejoin and re-split semantically.
    if(v.length>=4){
      const strs=v.filter(x=>typeof x==='string');
      if(strs.length===v.length){
        const singles=strs.filter(s=>s.length<=1).length;
        if(singles/strs.length>=0.8){
          const joined=strs.join('');
          return joined.split(/[,;\n]/).map(s=>s.trim()).filter(Boolean);
        }
      }
    }
    return v;
  }
  if(typeof v==='string'){
    return v.split(/[,;\n]/).map(s=>s.trim()).filter(Boolean);
  }
  return [v];
}
// Deep-clean a resume dict in place: rebuild every char-split list (where an
// upstream `list(<string>)` shredded a sentence into single chars), and split
// the recovered string back on common delimiters. Idempotent — safe to call
// repeatedly from editor, preview, and download paths.
function normalizeResume(r){
  if(!r||typeof r!=='object')return r;
  const fix=(v)=>{
    if(Array.isArray(v)){
      if(v.length>=4&&v.every(x=>typeof x==='string')){
        const singles=v.filter(s=>s.length<=1).length;
        if(singles/v.length>=0.8){
          const joined=v.join('').trim();
          if(joined){
            const parts=joined.split(/[,;\n]/).map(s=>s.trim()).filter(Boolean);
            return parts.length?parts:[joined];
          }
        }
      }
      return v.map(fix);
    }
    if(v&&typeof v==='object'){
      const out={};for(const k in v)out[k]=fix(v[k]);return out;
    }
    return v;
  };
  return fix(r);
}

function urlize(v){
  v=ss(v).trim();
  if(!v)return'';
  if(/^https?:\/\//.test(v))return v;
  if(/@/.test(v))return'mailto:'+v;
  return'https://'+v;
}
function linkify(label,raw,display){
  if(!raw)return'';
  const url=urlize(raw);
  const disp=display||ss(raw).replace(/^https?:\/\//,'').replace(/\/$/,'');
  return`<a class="pv-link" href="${esc(url)}" target="_blank" rel="noopener">${esc(disp)}</a>`;
}
function bullets(arr){
  return toArr(arr).map(b=>{
    const s=ss(b);return s?`<div class="pv-b">${esc(s)}</div>`:'';
  }).join('');
}
function tags(arr){
  return toArr(arr).map(t=>{const s=ss(t);return s?`<span class="stag">${esc(s)}</span>`:''}).join('');
}

function buildPv(resume){
  const pi=resume.personal_info||{};
  const contactBits=[];
  ['email','phone','location'].forEach(k=>{const v=ss(pi[k]);if(v)contactBits.push(esc(v));});
  ['linkedin','github','website','portfolio'].forEach(k=>{const v=ss(pi[k]);if(v)contactBits.push(linkify(k,v));});
  const head=`<div class="pv-head">
    <div class="pv-name">${esc(ss(pi.full_name))||'Your Name'}</div>
    ${ss(pi.professional_title)?`<div class="pv-role">${esc(ss(pi.professional_title))}</div>`:''}
    ${contactBits.length?`<div class="pv-contact">${contactBits.join(' &nbsp;·&nbsp; ')}</div>`:''}
  </div>`;

  const sections=[];

  // Summary
  const summary=ss(resume.professional_summary);
  if(summary){
    sections.push(`<div class="pv-sec"><div class="pv-st">Professional Summary</div>
      <div class="pv-sum">${esc(summary)}</div></div>`);
  }

  // Core Competencies
  const comps=toArr(resume.core_competencies).map(ss).filter(Boolean);
  if(comps.length){
    sections.push(`<div class="pv-sec"><div class="pv-st">Core Competencies</div>
      <div class="pv-comp-grid">${comps.map(c=>`<div class="pv-comp-item">${esc(c)}</div>`).join('')}</div></div>`);
  }

  // Experience
  const exp=toArr(resume.experience);
  if(exp.length){
    let h='<div class="pv-sec"><div class="pv-st">Professional Experience</div>';
    exp.forEach(e=>{
      const dates=`${esc(ss(e.start_date))} – ${esc(ss(e.end_date)||(e.current?'Present':'Present'))}`;
      const sub=[ss(e.company),ss(e.location),ss(e.employment_type)].filter(x=>x&&x.toLowerCase()!=='full-time').map(esc).join(' &nbsp;·&nbsp; ');
      const bs=[...toArr(e.responsibilities),...toArr(e.achievements)];
      const techs=toArr(e.technologies).map(ss).filter(Boolean);
      const teamSize=ss(e.team_size);
      const metaParts=[];
      if(teamSize)metaParts.push(`Team: ${esc(teamSize)}`);
      if(techs.length)metaParts.push(`Tech: ${esc(techs.join(', '))}`);
      h+=`<div class="pv-exp">
        <div class="pv-jt-row">
          <div><div class="pv-jt">${esc(ss(e.title))}</div>
          ${sub?`<div class="pv-co">${sub}</div>`:''}</div>
          <div class="pv-dt">${dates}</div>
        </div>
        ${bullets(bs)}
        ${metaParts.length?`<div class="pv-tech">${metaParts.join(' &nbsp;·&nbsp; ')}</div>`:''}
      </div>`;
    });
    h+='</div>';
    sections.push(h);
  }

  // Skills
  const tsk=resume.technical_skills||{};
  const skillsCats=[
    ['Languages',tsk.programming_languages],
    ['Frameworks & Libraries',tsk.frameworks_and_libraries],
    ['Databases',tsk.databases],
    ['Cloud & Infrastructure',tsk.cloud_and_infrastructure],
    ['DevOps & Tooling',tsk.devops_and_tools],
    ['Testing',tsk.testing],
    ['Methodologies',tsk.methodologies],
    ['Soft Skills',tsk.soft_skills],
  ].map(([l,v])=>[l,toArr(v)]).filter(([,v])=>v.length);
  if(skillsCats.length){
    let h='<div class="pv-sec"><div class="pv-st">Technical Skills</div>';
    skillsCats.forEach(([label,vals])=>{
      h+=`<div class="pv-skl"><div class="pv-skl-l">${esc(label)}</div>
        <div class="pv-skl-v">${esc(vals.map(ss).filter(Boolean).join(', '))}</div></div>`;
    });
    h+='</div>';
    sections.push(h);
  }

  // Projects
  const projs=toArr(resume.projects);
  if(projs.length){
    let h='<div class="pv-sec"><div class="pv-st">Projects</div>';
    projs.forEach(p=>{
      const url=p.url||p.github;
      const techs=toArr(p.technologies).map(ss).filter(Boolean);
      const projRole=ss(p.role);
      const projType=ss(p.type);
      const pStart=ss(p.start_date);
      const pEnd=ss(p.end_date);
      const projDates=pStart&&pEnd?`${esc(pStart)} – ${esc(pEnd)}`:(pStart||pEnd?esc(pStart||pEnd):'');
      const nameLc=(ss(p.name)||'').toLowerCase();
      const subParts=[];
      if(projRole&&!nameLc.includes(projRole.toLowerCase()))subParts.push(esc(projRole));
      if(projType&&!nameLc.includes(projType.toLowerCase()))subParts.push(`<span class="muted">${esc(projType)}</span>`);
      if(techs.length)subParts.push(esc(techs.join(', ')));
      h+=`<div class="pv-proj">
        <div class="pv-jt-row">
          <div><div class="pv-jt">${url?linkify('',url,ss(p.name)||'Project'):esc(ss(p.name))}</div>
          ${subParts.length?`<div class="pv-co">${subParts.join(' &nbsp;·&nbsp; ')}</div>`:''}</div>
          ${projDates?`<div class="pv-dt">${projDates}</div>`:''}
        </div>
        ${ss(p.description)?`<div class="pv-b">${esc(ss(p.description))}</div>`:''}
        ${bullets(p.highlights)}
      </div>`;
    });
    h+='</div>';
    sections.push(h);
  }

  // Open Source
  const oss_=toArr(resume.open_source_contributions);
  if(oss_.length){
    let h='<div class="pv-sec"><div class="pv-st">Open Source</div>';
    oss_.forEach(o=>{
      const ossSubParts=[];
      if(ss(o.role))ossSubParts.push(esc(ss(o.role)));
      if(ss(o.language))ossSubParts.push(`<span class="muted">${esc(ss(o.language))}</span>`);
      if(ss(o.stars))ossSubParts.push(`★ ${esc(ss(o.stars))}`);
      h+=`<div class="pv-os">
        <div class="pv-jt-row">
          <div><div class="pv-jt">${o.url?linkify('',o.url,ss(o.project)||'Project'):esc(ss(o.project))}</div>
          ${ossSubParts.length?`<div class="pv-co">${ossSubParts.join(' &nbsp;·&nbsp; ')}</div>`:''}</div>
        </div>
        ${ss(o.description)?`<div class="pv-b">${esc(ss(o.description))}</div>`:''}
        ${bullets(o.contributions)}
      </div>`;
    });
    h+='</div>';
    sections.push(h);
  }

  // Education
  const edu=toArr(resume.education);
  if(edu.length){
    let h='<div class="pv-sec"><div class="pv-st">Education</div>';
    edu.forEach(e=>{
      const deg=ss(e.degree)+(ss(e.field_of_study)?` in ${ss(e.field_of_study)}`:'');
      const dates=ss(e.start_date)&&ss(e.end_date)?`${esc(ss(e.start_date))} – ${esc(ss(e.end_date))}`:esc(ss(e.end_date)||ss(e.start_date)||'');
      const extras=[];
      if(ss(e.gpa))extras.push(`GPA: ${esc(ss(e.gpa))}`);
      if(ss(e.honors))extras.push(esc(ss(e.honors)));
      const cw=toArr(e.relevant_coursework).map(ss).filter(Boolean);
      if(cw.length)extras.push(`Coursework: ${esc(cw.join(', '))}`);
      const acts=toArr(e.activities).map(ss).filter(Boolean);
      h+=`<div class="pv-edu">
        <div class="pv-jt-row">
          <div><div class="pv-jt">${esc(deg)}</div>
          <div class="pv-co">${esc(ss(e.institution))}${ss(e.location)?` &nbsp;·&nbsp; ${esc(ss(e.location))}`:''}</div></div>
          <div class="pv-dt">${dates}</div>
        </div>
        ${extras.length?`<div class="pv-meta">${extras.join(' &nbsp;·&nbsp; ')}</div>`:''}
        ${acts.length?`<div class="pv-meta">Activities: ${esc(acts.join(', '))}</div>`:''}
      </div>`;
    });
    h+='</div>';
    sections.push(h);
  }

  // Certifications
  const certs=toArr(resume.certifications);
  if(certs.length){
    let h='<div class="pv-sec"><div class="pv-st">Certifications</div>';
    certs.forEach(c=>{
      const dateParts=[];
      if(ss(c.date))dateParts.push(`issued ${esc(ss(c.date))}`);
      if(ss(c.expiry))dateParts.push(`expires ${esc(ss(c.expiry))}`);
      const dateStr=dateParts.length?`<span class="muted"> &nbsp;(${dateParts.join(', ')})</span>`:'';
      const credId=ss(c.credential_id)?`<span class="muted"> &nbsp;ID: ${esc(ss(c.credential_id))}</span>`:'';
      h+=`<div class="pv-cert"><strong>${c.url?linkify('',c.url,ss(c.name)):esc(ss(c.name))}</strong>${ss(c.issuer)?` — ${esc(ss(c.issuer))}`:''  }${dateStr}${credId}</div>`;
    });
    h+='</div>';
    sections.push(h);
  }

  // Publications
  const pubs=toArr(resume.publications);
  if(pubs.length){
    let h='<div class="pv-sec"><div class="pv-st">Publications</div>';
    pubs.forEach(p=>{
      const pubTitleLc=(ss(p.title)||'').toLowerCase();
      const pubTypeRaw=ss(p.type);
      const pubType=(pubTypeRaw&&!pubTitleLc.includes(`[${pubTypeRaw.toLowerCase()}]`))?` <span class="muted">[${esc(pubTypeRaw)}]</span>`:'';
      const venue=ss(p.venue)?` — <em>${esc(ss(p.venue))}</em>`:'';
      const date=ss(p.date)?` (${esc(ss(p.date))})`:'';
      const authors=toArr(p.authors).map(ss).filter(Boolean);
      const authorsLine=authors.length?`<div class="pv-meta">${esc(authors.join(', '))}</div>`:'';
      h+=`<div class="pv-cert"><strong>${p.url?linkify('',p.url,ss(p.title)):esc(ss(p.title))}</strong>${pubType}${venue}${date}${authorsLine}</div>`;
    });
    h+='</div>';
    sections.push(h);
  }

  // Patents
  const patents=toArr(resume.patents);
  if(patents.length){
    let h='<div class="pv-sec"><div class="pv-st">Patents</div>';
    patents.forEach(p=>{
      const titleHtml=p.url?linkify('',p.url,ss(p.title)):esc(ss(p.title));
      h+=`<div class="pv-cert"><strong>${titleHtml}</strong>${ss(p.patent_number)?` — ${esc(ss(p.patent_number))}`:''}${ss(p.date)?` (${esc(ss(p.date))})`:''}
        ${ss(p.description)?`<div class="pv-b" style="padding-left:14px;color:var(--text3);font-size:11.5px">${esc(ss(p.description))}</div>`:''}</div>`;
    });
    h+='</div>';
    sections.push(h);
  }

  // Awards
  const awards=toArr(resume.awards_and_honors);
  if(awards.length){
    let h='<div class="pv-sec"><div class="pv-st">Awards & Honors</div>';
    awards.forEach(a=>{const v=ss(a);if(v)h+=`<div class="pv-b">${esc(v)}</div>`;});
    h+='</div>';
    sections.push(h);
  }

  // Volunteer
  const vols=toArr(resume.volunteer_experience);
  if(vols.length){
    let h='<div class="pv-sec"><div class="pv-st">Volunteer Experience</div>';
    vols.forEach(v=>{
      h+=`<div class="pv-exp">
        <div class="pv-jt-row">
          <div><div class="pv-jt">${esc(ss(v.role))}</div>
          ${ss(v.organization)?`<div class="pv-co">${esc(ss(v.organization))}</div>`:''}</div>
          <div class="pv-dt">${esc(ss(v.start_date))}${ss(v.end_date)?' – '+esc(ss(v.end_date)):''}</div>
        </div>
        ${ss(v.description)?`<div class="pv-b">${esc(ss(v.description))}</div>`:''}
      </div>`;
    });
    h+='</div>';
    sections.push(h);
  }

  // Languages
  const langs=toArr(resume.languages);
  if(langs.length){
    let h='<div class="pv-sec"><div class="pv-st">Languages</div><div>';
    h+=langs.map(l=>{const lang=ss(l.language);const prof=ss(l.proficiency);return lang?`<span class="stag">${esc(lang)}${prof?` (${esc(prof)})`:''}</span>`:'';}).join('');
    h+='</div></div>';
    sections.push(h);
  }

  // Interests
  const interests=toArr(resume.interests).map(ss).filter(Boolean);
  if(interests.length){
    sections.push(`<div class="pv-sec"><div class="pv-st">Interests</div>
      <div>${interests.map(i=>`<span class="stag">${esc(i)}</span>`).join('')}</div></div>`);
  }

  // References
  const refs=resume.references;
  if(refs){
    let refsHtml='';
    if(typeof refs==='string'){refsHtml=`<div class="pv-meta">${esc(refs)}</div>`;}
    else if(Array.isArray(refs)){refsHtml=refs.map(r=>{const s=ss(r);return s?`<div class="pv-b">${esc(s)}</div>`:''}).join('');}
    if(refsHtml)sections.push(`<div class="pv-sec"><div class="pv-st">References</div>${refsHtml}</div>`);
  }

  return`<div class="pv">${head}${sections.join('')||'<div class="pv-empty">No additional sections.</div>'}</div>`;
}

function synHl(json){
  let s=JSON.stringify(json,null,2).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  return s.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,m=>{
    if(/^"/.test(m))return/:$/.test(m)?`<span class="jk">${m}</span>`:`<span class="js">${m}</span>`;
    if(/true|false|null/.test(m))return`<span class="jb">${m}</span>`;
    return`<span class="jn">${m}</span>`;
  });
}

function renderMd(text){
  return esc(text)
    .replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')
    .replace(/__(.+?)__/g,'<strong>$1</strong>')
    .replace(/(?<![A-Za-z0-9])\*([^*\n]+)\*(?![A-Za-z0-9])/g,'<em>$1</em>')
    .replace(/(?<![A-Za-z0-9])_([^_\n]+)_(?![A-Za-z0-9])/g,'<em>$1</em>')
    .replace(/`(.+?)`/g,'<code style="font-family:var(--mono);font-size:12px;background:var(--bg3);padding:1px 5px;border-radius:4px">$1</code>')
    .replace(/^• (.+)$/gm,'<li>$1</li>')
    .replace(/^- (.+)$/gm,'<li>$1</li>')
    .replace(/(<li>.*<\/li>)/gs,'<ul>$1</ul>')
    .replace(/\n/g,'<br>');
}
function esc(s){if(!s&&s!==0)return'';return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
function scrollBot(){const c=document.getElementById('chat');requestAnimationFrame(()=>{c.scrollTop=c.scrollHeight;})}
function showToast(msg){const t=document.getElementById('toast');t.textContent=msg;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2400)}

function fmtMsgTime(ts){
  if(!ts)return'';
  const d=new Date(ts),now=new Date();
  const time=d.toLocaleTimeString([],{hour:'numeric',minute:'2-digit'});
  return d.toDateString()===now.toDateString()?time:d.toLocaleDateString([],{month:'short',day:'numeric'})+' · '+time;
}
function _attachCopyBtn(btn,text){
  btn.addEventListener('click',()=>{
    navigator.clipboard.writeText(text)
      .then(()=>showToast('✓ Copied'))
      .catch(()=>showToast('⚠ Copy failed'));
  });
}
function _msgMeta(ts,text,alignRight){
  const wrap=document.createElement('div');
  wrap.className='msg-meta';
  if(alignRight)wrap.style.justifyContent='flex-end';
  if(ts){const s=document.createElement('span');s.textContent=fmtMsgTime(ts);wrap.appendChild(s);}
  const btn=document.createElement('button');
  btn.className='msg-copy-btn';btn.title='Copy to clipboard';
  btn.innerHTML='<svg class="ic"><use href="#ic-copy"/></svg>';
  _attachCopyBtn(btn,text);
  wrap.appendChild(btn);
  return wrap;
}
function useEx(card){document.getElementById('mi').value=card.querySelector('.ex-txt').textContent;autoResize();document.getElementById('mi').focus()}
function appendHint(text){const i=document.getElementById('mi');const c=i.value.trim();i.value=c?c+'. '+text:text;autoResize();i.focus()}
function autoResize(){const ta=document.getElementById('mi');ta.style.height='auto';ta.style.height=Math.min(ta.scrollHeight,200)+'px'}

document.getElementById('mi').addEventListener('input',autoResize);
document.getElementById('mi').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMsg()}});
