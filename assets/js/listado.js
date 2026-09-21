(function () {
  var form = document.getElementById("filtros");
  var grilla = document.getElementById("grilla");
  if (!form || !grilla) return;

  var tarjetas = Array.prototype.slice.call(grilla.querySelectorAll(".tarjeta-propiedad"));
  var contador = document.getElementById("contador");
  var vacio = document.getElementById("sin-resultados");
  var campos = ["zona", "tipo", "ambientes", "precio", "orden"];

  var porDefecto = {};
  campos.forEach(function (c) { porDefecto[c] = form.elements[c].value; });

  var orden = {
    "precio-asc": function (a, b) { return a.dataset.precio - b.dataset.precio || a.dataset.orden - b.dataset.orden; },
    "precio-desc": function (a, b) { return b.dataset.precio - a.dataset.precio || a.dataset.orden - b.dataset.orden; },
    "amb-desc": function (a, b) { return b.dataset.ambientes - a.dataset.ambientes || a.dataset.orden - b.dataset.orden; },
    "amb-asc": function (a, b) { return a.dataset.ambientes - b.dataset.ambientes || a.dataset.orden - b.dataset.orden; },
    "sup-desc": function (a, b) { return b.dataset.superficie - a.dataset.superficie || a.dataset.orden - b.dataset.orden; }
  };

  function leerURL() {
    var q = new URLSearchParams(location.search);
    campos.forEach(function (c) {
      if (q.has(c)) form.elements[c].value = q.get(c);
    });
  }

  function escribirURL() {
    var q = new URLSearchParams();
    campos.forEach(function (c) {
      if (form.elements[c].value !== porDefecto[c]) q.set(c, form.elements[c].value);
    });
    var s = q.toString();
    history.replaceState(null, "", s ? "?" + s : location.pathname);
  }

  function cumple(t) {
    var d = t.dataset;
    var zona = form.elements.zona.value;
    var tipo = form.elements.tipo.value;
    var amb = form.elements.ambientes.value;
    var precioMax = Number(form.elements.precio.value) || Infinity;

    if (zona && d.zona !== zona) return false;
    if (tipo && d.tipo !== tipo) return false;
    if (amb === "5" && Number(d.ambientes) < 5) return false;
    if (amb && amb !== "5" && Number(d.ambientes) !== Number(amb)) return false;
    return Number(d.precio) <= precioMax;
  }

  function aplicar() {
    var cmp = orden[form.elements.orden.value] || orden["precio-asc"];
    var visibles = 0;
    tarjetas.slice().sort(cmp).forEach(function (t) {
      grilla.appendChild(t);
      t.hidden = !cumple(t);
      if (!t.hidden) visibles++;
    });
    contador.textContent = visibles + (visibles === 1 ? " propiedad" : " propiedades");
    vacio.hidden = visibles > 0;
    escribirURL();
  }

  function limpiar() {
    form.reset();
    aplicar();
  }

  form.addEventListener("input", aplicar);
  form.addEventListener("change", aplicar);
  form.addEventListener("submit", function (e) { e.preventDefault(); });
  Array.prototype.forEach.call(document.querySelectorAll(".js-limpiar"), function (b) {
    b.addEventListener("click", limpiar);
  });

  leerURL();
  aplicar();
})();
