// ADM Auth Guard — verifica sessão no servidor, redireciona se não autenticado
(function () {
  var autenticado = sessionStorage.getItem('adm_auth') === '1';
  if (!autenticado) {
    // fallback: consulta servidor síncrono
    try {
      var x = new XMLHttpRequest();
      x.open('GET', '/api/auth/verificar', false);
      x.timeout = 2000;
      x.send();
      if (x.status === 200) {
        var d = JSON.parse(x.responseText);
        autenticado = d.autenticado;
        if (autenticado) sessionStorage.setItem('adm_auth', '1');
      }
    } catch (e) {}
  }
  if (!autenticado) {
    sessionStorage.setItem('adm_return', window.location.href);
    window.location.replace('/#adm');
  }
})();
