"""Genera las páginas de detalle de cada propiedad a partir de data/propiedades.json.

Uso (desde la raíz del repositorio):
    python _build/build.py

- Lee data/propiedades.json y la plantilla _build/plantilla_propiedad.html.
- Escribe ventas/ven_<id>.html (y alquileres/alq_<id>.html para operacion "alquiler").
- Las fotos se toman de assets/img/<ventas|alquileres>/<id>/01.jpg, 02.jpg, ...
  y se crean miniaturas en .../<id>/thumbs/ (solo si faltan o la foto cambió).
- Sincroniza el campo "fotos" del JSON con la cantidad real de fotos en la carpeta.

Requiere Pillow:  pip install pillow
"""
import html
import json
import os
import urllib.parse

from PIL import Image, ImageOps

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOMINIO = "https://agostinoprop.com.ar"
WHATSAPP = "5491168042437"
LADO_MINIATURA = 600

OPERACIONES = {
    "venta": ("ventas", "ven_", "Venta"),
    "alquiler": ("alquileres", "alq_", "Alquiler"),
}

NOTA_COTI = (
    "La venta de este inmueble está sujeta a la tramitación del Código de Transferencia "
    "de Inmuebles (COTI), de conformidad con la normativa vigente (Res AFIP 2371/08, "
    "2439/08 y ccs.) por parte del propietario."
)

esc = html.escape


def numero(n):
    return f"{n:,}".replace(",", ".")


def precio(p):
    return ("U$D " if p["moneda"] == "USD" else "$ ") + numero(p["precio"])


def anios(n):
    return "1 año" if n == 1 else f"{n} años"


def listar_fotos(p, carpeta):
    base = os.path.join(RAIZ, "assets", "img", carpeta, p["id"])
    fotos = []
    i = 1
    while os.path.exists(os.path.join(base, f"{i:02d}.jpg")):
        nombre = f"{i:02d}.jpg"
        ruta = os.path.join(base, nombre)
        ruta_min = os.path.join(base, "thumbs", nombre)
        if not os.path.exists(ruta_min) or os.path.getmtime(ruta_min) < os.path.getmtime(ruta):
            with Image.open(ruta) as im:
                min_ = ImageOps.exif_transpose(im).convert("RGB")
            min_.thumbnail((LADO_MINIATURA, LADO_MINIATURA))
            os.makedirs(os.path.dirname(ruta_min), exist_ok=True)
            min_.save(ruta_min, "JPEG", quality=80, optimize=True, progressive=True)
        with Image.open(ruta) as im:
            w, h = ImageOps.exif_transpose(im).size
        with Image.open(ruta_min) as im:
            tw, th = im.size
        url_base = f"/assets/img/{carpeta}/{p['id']}"
        fotos.append(dict(n=i, w=w, h=h, tw=tw, th=th,
                          url=f"{url_base}/{nombre}", thumb=f"{url_base}/thumbs/{nombre}"))
        i += 1
    sueltas = [f for f in os.listdir(base) if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))] if os.path.isdir(base) else []
    if len(sueltas) != len(fotos):
        print(f"  AVISO {p['id']}: hay {len(sueltas)} archivos de imagen pero se usan {len(fotos)} "
              f"(deben llamarse 01.jpg, 02.jpg... sin saltear números)")
    return fotos


def html_galeria(p, fotos):
    n = len(fotos)
    if n == 0:
        return ""
    m = min(n - 1, 4)
    items = []
    for i, f in enumerate(fotos):
        clases = "galeria-item" + (" galeria-extra" if i >= 5 else "")
        if i == 0:
            src, w, h, carga = f["url"], f["w"], f["h"], "eager"
        else:
            src, w, h, carga = f["thumb"], f["tw"], f["th"], "lazy"
        alt = f"Foto {f['n']} de {p['titulo']}"
        mas = f'<span class="galeria-mas">+{n - 5} fotos</span>' if (i == 4 and n > 5) else ""
        items.append(
            f'        <a class="{clases}" href="{f["url"]}" data-pswp-width="{f["w"]}" '
            f'data-pswp-height="{f["h"]}" target="_blank" rel="noopener">'
            f'<img src="{src}" width="{w}" height="{h}" alt="{esc(alt)}" loading="{carga}" decoding="async" />{mas}</a>'
        )
    boton = ""
    if n > 5:
        boton = (
            '      <div class="text-center mt-3">\n'
            f'        <button type="button" class="btn btn-outline-danger" id="galeria-toggle" data-total="{n}">'
            f"Ver todas las fotos ({n})</button>\n"
            "      </div>\n"
        )
    return (
        f'      <div class="galeria galeria--m{m}" id="galeria">\n' + "\n".join(items) + "\n      </div>\n" + boton
    )


def html_resumen(p):
    filas = []

    def add(etiqueta, valor):
        if valor is not None:
            filas.append(f"<div><small>{esc(etiqueta)}</small><strong>{esc(str(valor))}</strong></div>")

    add("Tipo", p["tipo"])
    add("Sup. total", f"{p['sup_total']} m²" if p["sup_total"] else None)
    add("Sup. cubierta", f"{p['sup_cubierta']} m²" if p["sup_cubierta"] else None)
    add("Ambientes", p["ambientes"])
    add("Dormitorios", p["dormitorios"])
    add("Baños", p["banos"])
    add("Cocheras", p["cocheras"])
    add("Antigüedad", anios(p["antiguedad"]) if p["antiguedad"] else None)

    expensas = f'<p class="propiedad-expensas">Expensas: $ {numero(p["expensas"])}</p>' if p.get("expensas") else ""
    etiquetas = ""
    if p["extras"]:
        etiquetas = '<div class="propiedad-etiquetas">' + "".join(f"<span>{esc(x)}</span>" for x in p["extras"]) + "</div>"
    estado = ""
    if p["estado"] != "disponible":
        estado = f'<div class="alert alert-danger text-center mb-3"><strong>{esc(p["estado"].upper())}</strong></div>'

    url = f"{DOMINIO}/{OPERACIONES[p['operacion']][0]}/{OPERACIONES[p['operacion']][1]}{p['id']}.html"
    texto = f"Hola! Me interesa la propiedad: {p['titulo']} ({url})"
    wa = f"https://wa.me/{WHATSAPP}?text={urllib.parse.quote(texto)}"

    return (
        '        <div class="content-card p-4 propiedad-resumen">\n'
        f"          {estado}\n"
        f'          <p class="propiedad-operacion">{esc(OPERACIONES[p["operacion"]][2])}</p>\n'
        f'          <p class="propiedad-precio">{esc(precio(p))}</p>\n'
        f"          {expensas}\n"
        f'          <div class="propiedad-datos">{"".join(filas)}</div>\n'
        f"          {etiquetas}\n"
        f'          <a class="btn btn-success btn-block mt-3" href="{wa}" target="_blank" rel="noopener">✆ Consultar por WhatsApp</a>\n'
        '          <a class="btn btn-danger btn-block" href="/contacto.html">Contáctanos</a>\n'
        "        </div>\n"
    )


def html_caracteristicas(p):
    tarjetas = []
    for titulo, items in p["caracteristicas"].items():
        lis = "".join(f"<li>{esc(x)}</li>" for x in items)
        tarjetas.append(
            '          <div class="col-12 col-sm-6 mb-4">\n'
            '            <div class="content-card p-3 h-100">\n'
            f"              <h5>{esc(titulo)}</h5>\n"
            f'              <ul class="lista-caracteristicas">{lis}</ul>\n'
            "            </div>\n"
            "          </div>\n"
        )
    return '        <div class="row mt-4">\n' + "".join(tarjetas) + "        </div>\n" if tarjetas else ""


def render(p, plantilla):
    carpeta, prefijo, etiqueta_op = OPERACIONES[p["operacion"]]
    fotos = listar_fotos(p, carpeta)
    url = f"{DOMINIO}/{carpeta}/{prefijo}{p['id']}.html"
    ubicacion = f"{p['direccion']}, {p['barrio']}, {p['partido']}"

    desc_meta = f"{p['titulo']} - {p['barrio']}, {p['partido']}. {precio(p)}. Agostino Propiedades, Ramos Mejía."
    parrafos = "".join(f"        <p>{esc(x)}</p>\n" for x in p["descripcion"])
    mapa = ""
    if p.get("mapa"):
        mapa = (
            '        <h4 class="mt-2 mb-3">Ubicación</h4>\n'
            '        <div class="responsive-iframe mb-4">\n'
            f'          <iframe src="{esc(p["mapa"])}" style="border: 0" allowfullscreen loading="lazy" '
            'title="Ubicación en el mapa"></iframe>\n'
            "        </div>\n"
        )
    coti = f'        <p class="propiedad-nota">{esc(NOTA_COTI)}</p>\n' if p["operacion"] == "venta" else ""

    contenido = (
        '    <div class="container mt-4 mb-5">\n'
        f'      <a class="propiedad-volver" href="/{carpeta}.html">&larr; Volver a {esc(carpeta)}</a>\n'
        f'      <h1 class="h2 mt-3">{esc(p["titulo"])}</h1>\n'
        f'      <h4 class="propiedad-ubicacion">📍 {esc(ubicacion)}</h4>\n\n'
        + html_galeria(p, fotos)
        + '\n      <div class="row mt-4">\n'
        '        <div class="col-12 col-lg-4 order-lg-2 mb-4">\n'
        + html_resumen(p)
        + "        </div>\n"
        '        <div class="col-12 col-lg-8 order-lg-1">\n'
        + parrafos
        + html_caracteristicas(p)
        + mapa
        + coti
        + "        </div>\n"
        "      </div>\n"
        "    </div>"
    )

    salida = (
        plantilla.replace("{{TITULO_PAGINA}}", esc(f"{p['titulo']} | Agostino Propiedades"))
        .replace("{{DESCRIPCION_META}}", esc(desc_meta))
        .replace("{{URL}}", url)
        .replace("{{OG_IMAGEN}}", DOMINIO + fotos[0]["url"] if fotos else "")
        .replace("{{OPERACION}}", etiqueta_op)
        .replace("{{CONTENIDO}}", contenido)
    )
    ruta = os.path.join(RAIZ, carpeta, f"{prefijo}{p['id']}.html")
    with open(ruta, "w", encoding="utf-8", newline="\n") as f:
        f.write(salida)
    return ruta, len(fotos)


def main():
    ruta_json = os.path.join(RAIZ, "data", "propiedades.json")
    with open(ruta_json, encoding="utf-8") as f:
        propiedades = json.load(f)
    with open(os.path.join(RAIZ, "_build", "plantilla_propiedad.html"), encoding="utf-8") as f:
        plantilla = f.read()

    cambio = False
    for p in propiedades:
        ruta, n = render(p, plantilla)
        if p.get("fotos") != n:
            print(f"  fotos de {p['id']}: {p.get('fotos')} -> {n}")
            p["fotos"] = n
            cambio = True
        print(f"OK {os.path.relpath(ruta, RAIZ)} ({n} fotos)")

    if cambio:
        with open(ruta_json, "w", encoding="utf-8", newline="\n") as f:
            json.dump(propiedades, f, ensure_ascii=False, indent=2)
            f.write("\n")
    print(f"Listo: {len(propiedades)} páginas generadas.")


if __name__ == "__main__":
    main()
