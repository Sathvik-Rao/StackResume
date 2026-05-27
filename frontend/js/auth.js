// ── Auth interceptor ────────────────────────────────────────────────────────
// When AUTH_ENABLED=true, every request carries Authorization: Bearer <token>.
// The token is a server-issued UUID session token stored in sessionStorage so
// it survives page refreshes but is cleared when the tab is closed.
const AUTH_KEY='sr_auth';
const _origFetch=window.fetch.bind(window);
window.fetch=function(input,init){
  init=init||{};
  const tok=sessionStorage.getItem(AUTH_KEY);
  if(tok){
    init.headers=Object.assign({},init.headers||{},{Authorization:'Bearer '+tok});
  }
  return _origFetch(input,init).then(resp=>{
    if(resp.status===401){
      const url=typeof input==='string'?input:input.url;
      if(url.indexOf('/api/')>=0&&url.indexOf('/api/auth/')<0){
        showLogin('Your session has expired. Please sign in again.');
      }
    }
    return resp;
  });
};

// SHA-512 using the browser's native SubtleCrypto — no library needed.
async function sha512hex(str){
  const buf=await crypto.subtle.digest('SHA-512',new TextEncoder().encode(str));
  return Array.from(new Uint8Array(buf)).map(b=>b.toString(16).padStart(2,'0')).join('');
}

function showLogin(msg){
  // Clear any stale token so the fetch interceptor stops sending it.
  sessionStorage.removeItem(AUTH_KEY);
  document.getElementById('logout-btn').style.display='none';
  document.getElementById('login-err').style.display=msg?'block':'none';
  if(msg)document.getElementById('login-err').textContent=msg;
  document.getElementById('login-modal').classList.add('open');
  setTimeout(()=>document.getElementById('login-user').focus(),50);
}

async function doLogin(){
  const u=document.getElementById('login-user').value.trim();
  const p=document.getElementById('login-pass').value;
  if(!u||!p){showLogin('Username and password required');return;}
  let pwHash;
  try{pwHash=await sha512hex(p);}
  catch(e){showLogin('Hashing failed: '+e.message);return;}
  try{
    const r=await _origFetch('/api/auth/login',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({username:u,password_hash:pwHash}),
    });
    const d=await r.json();
    if(r.ok&&d.token){
      sessionStorage.setItem(AUTH_KEY,d.token);
      document.getElementById('login-modal').classList.remove('open');
      document.getElementById('login-err').style.display='none';
      document.getElementById('login-pass').value='';
      if(d.user){
        document.getElementById('logout-user').textContent=d.user;
        document.getElementById('logout-btn').style.display='flex';
      }
      init();
    }else{
      showLogin(d.detail||'Invalid credentials');
    }
  }catch(e){
    showLogin('Login failed: '+e.message);
  }
}

function doLogout(){
  // Two-step: open a confirmation modal so accidental clicks don't kill the session.
  document.getElementById('logout-modal').classList.add('open');
}
function cancelLogout(){
  document.getElementById('logout-modal').classList.remove('open');
}
async function confirmLogout(){
  const btn=document.getElementById('logout-confirm-btn');
  btn.disabled=true;btn.textContent='Signing out…';
  try{await fetch('/api/auth/logout',{method:'POST'});}catch(e){}
  sessionStorage.removeItem(AUTH_KEY);
  document.getElementById('logout-btn').style.display='none';
  document.getElementById('logout-user').textContent='';
  document.getElementById('logout-modal').classList.remove('open');
  btn.disabled=false;btn.textContent='Sign out';
  showLogin();
}

document.addEventListener('keydown',e=>{
  if(document.getElementById('login-modal').classList.contains('open')&&e.key==='Enter'){
    e.preventDefault();doLogin();
  }
});

async function _checkAuth(){
  try{
    const tok=sessionStorage.getItem(AUTH_KEY);
    const r=await _origFetch('/api/auth/check',{
      headers:tok?{Authorization:'Bearer '+tok}:{},
    });
    if(!r.ok&&r.status===401){showLogin();return false;}
    if(r.ok&&tok){
      const d=await r.json().catch(()=>({}));
      if(d.user)document.getElementById('logout-user').textContent=d.user;
      document.getElementById('logout-btn').style.display='flex';
    }
    return true;
  }catch(e){return true;}
}
