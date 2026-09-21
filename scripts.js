jQuery('document').ready(function($){

  var menuBtn = $('.menu-icon'),
      menu = $('.navigation ul');


  menuBtn.click(function(){

    if(menu.hasClass('show')){
        menu.removeClass('show');
    }else{
        menu.addClass('show');
    }

  });

  var ruta = location.pathname.replace(/index\.html$/, '');
  $('.navigation a').each(function () {
    var destino = this.pathname.replace(/index\.html$/, '');
    var seccion = destino !== '/' && ruta.indexOf(destino.replace(/\.html$/, '')) === 0;
    if (destino === ruta || seccion) {
      $(this).addClass('activa');
    }
  });

  // Eventos de Google Analytics (si no está cargado, no hacen nada)
  function evento(nombre, parametros) {
    if (typeof gtag === 'function') { gtag('event', nombre, parametros); }
  }

  // Clics en cualquier enlace a WhatsApp, indicando de dónde salió
  $(document).on('click', 'a[href*="wa.me"]', function () {
    var link = $(this);
    var lugar = 'contenido';
    if (link.closest('.topbar').length) { lugar = 'barra_superior'; }
    else if (link.closest('.wsp-flotante').length || link.hasClass('wsp-flotante')) { lugar = 'boton_flotante'; }
    else if (link.closest('.pie').length) { lugar = 'pie'; }
    evento('clic_whatsapp', { ubicacion: lugar, pagina: location.pathname });
  });

  // Formularios que se envían con Web3Forms (form[data-web3])
  $('form[data-web3]').each(function () {
    var form = $(this);
    var button = form.find('button[type="submit"]');
    var textoBoton = button.text();
    var mensajeOk = form.data('ok') || '¡Gracias! Tu mensaje fue enviado, te vamos a contactar a la brevedad.';
    var mensajeError = 'No se pudo enviar el mensaje. Probá de nuevo o contactanos por WhatsApp.';

    form.on('submit', function (e) {
      e.preventDefault();

      var status = form.find('.form-estado');
      button.prop('disabled', true).text('Enviando...');
      status.removeClass('alert alert-success alert-danger').text('');

      fetch(form.attr('action'), {
        method: 'POST',
        body: new FormData(form[0]),
        headers: { Accept: 'application/json' }
      })
        .then(function (res) { return res.json(); })
        .then(function (data) {
          if (data.success) {
            status.addClass('alert alert-success').text(mensajeOk);
            evento('generate_lead', { formulario: form.hasClass('tasacion-form') ? 'tasacion' : 'contacto' });
            form[0].reset();
          } else {
            status.addClass('alert alert-danger').text(mensajeError);
          }
        })
        .catch(function () {
          status.addClass('alert alert-danger').text(mensajeError);
        })
        .finally(function () {
          button.prop('disabled', false).text(textoBoton);
        });
    });
  });
});
