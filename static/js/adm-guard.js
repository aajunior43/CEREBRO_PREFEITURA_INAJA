// ADM Auth Guard — verifica sessao no servidor, redireciona para login.html se nao for admin
(function () {
  if (sessionStorage.getItem('adm_auth') === '1' && sessionStorage.getItem('user_nivel') === 'admin') {
    return;
  }
  try {
    var x = new XMLHttpRequest();
    x.open('GET', '/api/auth/verificar', false);
    x.timeout = 3000;
    x.send();
    if (x.status === 200) {
      var d = JSON.parse(x.responseText);
      if (d.autenticado) {
        sessionStorage.setItem('adm_auth', '1');
        sessionStorage.setItem('user_nome', d.nome || '');
        sessionStorage.setItem('user_nivel', d.nivel || '');
        if (d.nivel === 'admin') return;
      }
    }
  } catch (e) {}
  sessionStorage.setItem('adm_return', window.location.href);
  window.location.replace('/login.html');
})();
