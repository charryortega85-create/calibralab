/* Visor de la consulta por QR: dibuja cada hoja en un lienzo y dificulta guardarla, copiarla o
   imprimirla. Ninguna página web puede impedir del todo una captura de pantalla del teléfono;
   por eso cada hoja lleva además una marca de agua con la fecha y la hora. */
(function () {
  var visor = document.getElementById('visor');
  if (!visor) return;

  visor.querySelectorAll('canvas[data-src]').forEach(function (lienzo) {
    fetch(lienzo.dataset.src, {credentials: 'same-origin', cache: 'no-store'})
      .then(function (r) { if (!r.ok) throw new Error(); return r.blob(); })
      .then(function (b) { return createImageBitmap(b); })
      .then(function (img) {
        lienzo.width = img.width; lienzo.height = img.height;
        lienzo.getContext('2d').drawImage(img, 0, 0);
        lienzo.removeAttribute('data-src');
      })
      .catch(function () { lienzo.replaceWith(Object.assign(document.createElement('p'), {
        className: 'cell-sub', textContent: 'No se pudo mostrar esta hoja.'})); });
  });

  ['contextmenu', 'dragstart', 'selectstart', 'copy'].forEach(function (ev) {
    document.addEventListener(ev, function (e) { e.preventDefault(); });
  });
  document.addEventListener('keydown', function (e) {
    var k = (e.key || '').toLowerCase();
    if ((e.ctrlKey || e.metaKey) && ['s', 'p', 'c'].indexOf(k) >= 0) e.preventDefault();
    if (k === 'printscreen') { ocultar(); e.preventDefault(); }
  });
  document.addEventListener('keyup', function (e) {
    if ((e.key || '').toLowerCase() === 'printscreen') {
      try { navigator.clipboard.writeText(''); } catch (err) { /* sin permiso: no importa */ }
    }
  });

  /* Al pasar a otra ventana (herramienta de recortes, grabador de pantalla) el certificado se oculta. */
  function ocultar() { document.body.classList.add('visor-oculto'); }
  function mostrar() { document.body.classList.remove('visor-oculto'); }
  window.addEventListener('blur', ocultar);
  window.addEventListener('focus', mostrar);
  document.addEventListener('visibilitychange', function () { document.hidden ? ocultar() : mostrar(); });
  window.addEventListener('beforeprint', ocultar);
  window.addEventListener('afterprint', mostrar);
})();
