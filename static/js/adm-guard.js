// ADM Auth Guard — run before page renders
(function () {
  if (!sessionStorage.getItem('adm_auth')) {
    sessionStorage.setItem('adm_return', window.location.href);
    window.location.replace('/#adm');
  }
})();
