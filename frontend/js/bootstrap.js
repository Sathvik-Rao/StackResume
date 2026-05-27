// Bootstrap: check auth first; init() runs only if we're allowed in.
(async()=>{
  const ok=await _checkAuth();
  if(ok)init();
})();
