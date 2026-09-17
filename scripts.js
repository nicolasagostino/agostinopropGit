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

  var form = $('#form-contacto');
  if (form.length) {
    form.on('submit', function (e) {
      e.preventDefault();

      var status = $('#form-status');
      var button = form.find('button[type="submit"]');
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
            status.addClass('alert alert-success').text('¡Gracias! Tu mensaje fue enviado, te vamos a contactar a la brevedad.');
            form[0].reset();
          } else {
            status.addClass('alert alert-danger').text('No se pudo enviar el mensaje. Probá de nuevo o contactanos por WhatsApp.');
          }
        })
        .catch(function () {
          status.addClass('alert alert-danger').text('No se pudo enviar el mensaje. Probá de nuevo o contactanos por WhatsApp.');
        })
        .finally(function () {
          button.prop('disabled', false).text('Enviar');
        });
    });
  }
});