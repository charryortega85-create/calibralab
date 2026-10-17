/* CalibraLab: menú en pantallas chicas y tema claro/oscuro (sin librerías externas). */
(function () {
  'use strict';
  var $ = function (s) { return document.querySelector(s); };
  var sidebar = $('#sidebar'), scrim = $('#scrim'), menuBtn = $('#menuBtn'), themeBtn = $('#themeBtn');

  function abrir() { sidebar.classList.add('open'); scrim.classList.add('show'); menuBtn.setAttribute('aria-expanded', 'true'); }
  function cerrar() { sidebar.classList.remove('open'); scrim.classList.remove('show'); menuBtn.setAttribute('aria-expanded', 'false'); }
  if (menuBtn) {
    menuBtn.addEventListener('click', function () { sidebar.classList.contains('open') ? cerrar() : abrir(); });
    scrim.addEventListener('click', cerrar);
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') cerrar(); });
  }

  function aplicarTema(t) {
    document.documentElement.setAttribute('data-theme', t);
    if (!themeBtn) return;
    themeBtn.innerHTML = '<svg class="i" aria-hidden="true"><use href="#' + (t === 'dark' ? 'i-sun' : 'i-moon') + '"/></svg>';
    themeBtn.setAttribute('aria-label', t === 'dark' ? 'Cambiar a tema claro' : 'Cambiar a tema oscuro');
  }
  aplicarTema(document.documentElement.getAttribute('data-theme') || 'light');
  if (themeBtn) {
    themeBtn.addEventListener('click', function () {
      var t = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      aplicarTema(t);
      try { localStorage.setItem('calibralab-tema', t); } catch (e) {}
    });
  }

  // Ver u ocultar la contraseña mientras se escribe.
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('.pass-ver');
    if (!btn) return;
    var input = btn.parentNode.querySelector('input');
    var ver = input.type === 'password';
    input.type = ver ? 'text' : 'password';
    var texto = ver ? 'Ocultar la contraseña' : 'Mostrar la contraseña';
    btn.setAttribute('aria-pressed', ver ? 'true' : 'false');
    btn.setAttribute('aria-label', texto);
    btn.title = texto;
    btn.querySelector('use').setAttribute('href', ver ? '#i-eye-off' : '#i-eye');
    input.focus();
  });
})();
