/**
 * Respaldo de frame-ancestors para sitios sin cabeceras propias (GitHub Pages).
 * La directiva frame-ancestors de la CSP no se aplica cuando viene por <meta>, así que si este
 * sitio queda embebido en un iframe ajeno, se saca a sí mismo a la ventana principal.
 * En producción real (Caddy) esto nunca se ejecuta: X-Frame-Options/frame-ancestors ya lo impiden.
 */
(function () {
  "use strict";
  try {
    if (window.top !== window.self) {
      window.top.location.href = window.self.location.href;
    }
  } catch {
    // Acceso entre orígenes bloqueado por el propio navegador: igual estamos embebidos, salir.
    window.top.location.href = window.self.location.href;
  }
})();
