(function () {
  // Propiedades destacadas: cada visita ve 4 distintas, elegidas al azar
  var grilla = document.getElementById("destacadas-grilla");
  if (grilla) {
    var tarjetas = Array.prototype.slice.call(grilla.children);
    for (var i = tarjetas.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var t = tarjetas[i];
      tarjetas[i] = tarjetas[j];
      tarjetas[j] = t;
    }
    tarjetas.forEach(function (el) { grilla.appendChild(el); });
  }

  // Buscador: lleva a Ventas o Alquileres con los filtros ya aplicados
  var form = document.getElementById("buscador");
  if (!form) return;

  var opciones = JSON.parse(form.getAttribute("data-opciones"));
  var textoPrimero = { zona: "Todas", tipo: "Todos", precio: "Cualquiera" };

  function llenar(nombre, lista) {
    var select = form.elements[nombre];
    select.innerHTML = "";
    var vacio = document.createElement("option");
    vacio.value = "";
    vacio.textContent = textoPrimero[nombre];
    select.appendChild(vacio);
    lista.forEach(function (o) {
      var op = document.createElement("option");
      op.value = o[0];
      op.textContent = o[1];
      select.appendChild(op);
    });
  }

  form.elements.op.addEventListener("change", function () {
    var datos = opciones[form.elements.op.value];
    llenar("zona", datos.zonas);
    llenar("tipo", datos.tipos);
    llenar("precio", datos.precios);
  });

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var q = new URLSearchParams();
    ["zona", "tipo", "precio"].forEach(function (c) {
      if (form.elements[c].value) q.set(c, form.elements[c].value);
    });
    var base = form.elements.op.value === "alquiler" ? "/alquileres.html" : "/ventas.html";
    location.href = base + (q.toString() ? "?" + q.toString() : "");
  });
})();
