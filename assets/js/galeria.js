import PhotoSwipeLightbox from "/assets/vendor/photoswipe/photoswipe-lightbox.esm.min.js";

const galeria = document.getElementById("galeria");

if (galeria) {
  const lightbox = new PhotoSwipeLightbox({
    gallery: "#galeria",
    children: "a.galeria-item",
    pswpModule: () => import("/assets/vendor/photoswipe/photoswipe.esm.min.js"),
    showHideAnimationType: "fade",
    bgOpacity: 0.92,
    closeTitle: "Cerrar (Esc)",
    zoomTitle: "Acercar / alejar",
    arrowPrevTitle: "Anterior",
    arrowNextTitle: "Siguiente",
    errorMsg: "No se pudo cargar la foto",
    indexIndicatorSep: " / ",
  });
  lightbox.init();

  const boton = document.getElementById("galeria-toggle");
  if (boton) {
    boton.addEventListener("click", () => {
      const abierta = galeria.classList.toggle("galeria--todas");
      boton.textContent = abierta
        ? "Mostrar menos"
        : "Ver todas las fotos (" + boton.dataset.total + ")";
    });
  }
}
