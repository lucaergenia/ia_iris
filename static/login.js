document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('loginBtn');
  const email = document.getElementById('email');
  const pass = document.getElementById('password');
  const err = document.getElementById('loginError');

  async function doLogin(){
    err.textContent = '';
    try{
      const res = await fetch('/api/stats/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.value, password: pass.value })
      });
      if(!res.ok){
        const txt = await res.text();
        throw new Error(txt || 'Error al iniciar sesión');
      }
      window.location.href = '/';
    }catch(e){
      err.textContent = 'Credenciales inválidas';
    }
  }

  btn.addEventListener('click', doLogin);
  pass.addEventListener('keyup', (e)=>{ if(e.key==='Enter') doLogin(); });
});

