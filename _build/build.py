"""Genera las páginas del sitio que salen de data/propiedades.json.

Uso (desde la raíz del repositorio):
    python _build/build.py

Genera:
- ventas/ven_<id>.html y alquileres/alq_<id>.html: una página de detalle por propiedad.
- ventas.html y alquileres.html: los listados, con filtros y orden.
- index.html, tasaciones.html, quienessomos.html, contacto.html y 404.html, a partir de
  los archivos de _build/paginas/ (ahí se edita el contenido de esas páginas).
  Las opiniones de clientes salen de data/opiniones.json.
- sitemap.xml y robots.txt.

Las fotos se toman de assets/img/<ventas|alquileres>/<id>/01.jpg, 02.jpg, ...
Se crean miniaturas en .../<id>/thumbs/ (solo si faltan o la foto cambió) y se
sincroniza el campo "fotos" del JSON con la cantidad real de fotos de la carpeta.

Las páginas generadas no se editan a mano: se cambia el JSON o las plantillas
(_build/base.html) y se vuelve a correr este script.

Requiere Pillow:  pip install pillow
"""
import html
import json
import os
import sys
import urllib.parse

from PIL import Image, ImageOps

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validacion  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOMINIO = "https://agostinoprop.com.ar"
WHATSAPP = "5491168042437"
LADO_MINIATURA = 600
# Rangos del filtro de precio (moneda, tope de cada opción). Ajustar si cambian los precios del mercado.
PRECIOS_FILTRO = {
    "venta": ("U$D", [50000, 75000, 100000, 150000, 250000, 500000]),
    "alquiler": ("$", [500000, 800000, 1000000, 1500000, 2000000, 3000000]),
}

# operacion -> (carpeta, prefijo de archivo, etiqueta, título del listado, imagen del listado)
OPERACIONES = {
    "venta": ("ventas", "ven_", "Venta", "Ventas", "/assets/img/ventas.jpg"),
    "alquiler": ("alquileres", "alq_", "Alquiler", "Alquileres", "/assets/img/edificio.jpg"),
}

NOTA_COTI = (
    "La venta de este inmueble está sujeta a la tramitación del Código de Transferencia "
    "de Inmuebles (COTI), de conformidad con la normativa vigente (Res AFIP 2371/08, "
    "2439/08 y ccs.) por parte del propietario."
)

esc = html.escape


# ---------- utilidades ----------

def numero(n):
    return f"{n:,}".replace(",", ".")


def precio(p):
    return ("U$D " if p["moneda"] == "USD" else "$ ") + numero(p["precio"])


def anios(n):
    return "1 año" if n == 1 else f"{n} años"


def plural(n, singular, plural_):
    return f"{n} {singular if n == 1 else plural_}"


def url_pagina(p):
    carpeta, prefijo = OPERACIONES[p["operacion"]][:2]
    return f"/{carpeta}/{prefijo}{p['id']}.html"


def pagina(base, campos):
    for clave, valor in campos.items():
        base = base.replace("{{" + clave + "}}", valor)
    return base


def escribir(ruta_relativa, contenido):
    ruta = os.path.join(RAIZ, ruta_relativa)
    with open(ruta, "w", encoding="utf-8", newline="\n") as f:
        f.write(contenido)


# ---------- fotos ----------

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


def contar_fotos(p):
    carpeta = OPERACIONES[p["operacion"]][0]
    base = os.path.join(RAIZ, "assets", "img", carpeta, p["id"])
    n = 0
    while os.path.exists(os.path.join(base, f"{n + 1:02d}.jpg")):
        n += 1
    return n


def validar_datos(propiedades):
    """Revisa data/propiedades.json antes de generar. Si hay errores, se detiene con un mensaje claro."""
    errores, avisos = validacion.validar_todas(propiedades, contar_fotos)
    for a in avisos:
        print(f"  AVISO  {a['id']}: {a['mensaje']}")
    if errores:
        print("\nNo se generó nada porque hay errores en data/propiedades.json:")
        for e in errores:
            print(f"  ERROR  {e['id']} ({e['campo']}): {e['mensaje']}")
        sys.exit(1)


# ---------- página de detalle ----------

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
    return f'      <div class="galeria galeria--m{m}" id="galeria">\n' + "\n".join(items) + "\n      </div>\n" + boton


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

    texto = f"Hola! Me interesa la propiedad: {p['titulo']} ({DOMINIO}{url_pagina(p)})"
    wa = f"https://wa.me/{WHATSAPP}?text={urllib.parse.quote(texto)}"

    return (
        '        <div class="content-card p-4 propiedad-resumen">\n'
        f"          {estado}\n"
        f'          <p class="propiedad-operacion">{esc(OPERACIONES[p["operacion"]][2])}</p>\n'
        f'          <p class="propiedad-precio">{esc(precio(p))}</p>\n'
        f"          {expensas}\n"
        f'          <div class="propiedad-datos">{"".join(filas)}</div>\n'
        f"          {etiquetas}\n"
        f'          <a class="btn btn-success btn-block mt-3" href="{wa}" target="_blank" rel="noopener"><img class="ico-wsp" src="/assets/img/wpp.png" alt="" />Consultar por WhatsApp</a>\n'
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


def render_detalle(p, base):
    carpeta, prefijo, etiqueta_op = OPERACIONES[p["operacion"]][:3]
    fotos = listar_fotos(p, carpeta)
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
    barra = (
        '    <div class="cover cover-smaller d-flex justify-content-center p-2"\n'
        '         style="background-image:url(/assets/img/full_black.jpg)">\n'
        f"      <h2>{etiqueta_op}</h2>\n"
        "    </div>"
    )
    salida = pagina(base, dict(
        TITULO=esc(f"{p['titulo']} | Agostino Propiedades"),
        DESCRIPCION=esc(desc_meta),
        URL=DOMINIO + url_pagina(p),
        OG_IMAGEN=DOMINIO + fotos[0]["url"] if fotos else "",
        HEAD_EXTRA='    <link rel="stylesheet" href="/assets/vendor/photoswipe/photoswipe.css" />\n',
        DENTRO_HEADER="",
        DESPUES_HEADER=barra,
        CONTENIDO=contenido,
        SCRIPTS='    <script type="module" src="/assets/js/galeria.js"></script>',
    ))
    escribir(url_pagina(p).lstrip("/"), salida)
    escribir(nombre_redireccion(p), html_redireccion(p, desc_meta, fotos))
    return len(fotos)


def nombre_redireccion(p):
    # Antes las páginas estaban en la raíz (/ven_x.html): esos links siguen andando (QRs, WhatsApp, Google).
    return os.path.basename(url_pagina(p))


def html_redireccion(p, descripcion, fotos):
    nuevo = url_pagina(p)
    titulo = esc(f"{p['titulo']} | Agostino Propiedades")
    imagen = f'    <meta property="og:image" content="{DOMINIO + fotos[0]["url"]}" />\n' if fotos else ""
    return (
        "<!DOCTYPE html>\n"
        "<!-- Redirección desde la dirección vieja. Generada por _build/build.py. No editar a mano. -->\n"
        '<html lang="es">\n'
        "  <head>\n"
        '    <meta charset="utf-8" />\n'
        f"    <title>{titulo}</title>\n"
        f'    <meta name="description" content="{esc(descripcion)}" />\n'
        '    <meta name="robots" content="noindex" />\n'
        f'    <link rel="canonical" href="{DOMINIO + nuevo}" />\n'
        f'    <meta http-equiv="refresh" content="0; url={nuevo}" />\n'
        '    <meta property="og:type" content="website" />\n'
        '    <meta property="og:site_name" content="Agostino Propiedades" />\n'
        f'    <meta property="og:title" content="{titulo}" />\n'
        f'    <meta property="og:description" content="{esc(descripcion)}" />\n'
        f'    <meta property="og:url" content="{DOMINIO + nuevo}" />\n'
        f"{imagen}"
        f'    <script>location.replace("{nuevo}" + location.search + location.hash);</script>\n'
        "  </head>\n"
        f'  <body><p>Esta propiedad está ahora en <a href="{nuevo}">{DOMINIO + nuevo}</a>.</p></body>\n'
        "</html>\n"
    )


# ---------- listados ----------

def linea_resumen(p):
    partes = [p["tipo"]]
    sup = p["sup_cubierta"] or p["sup_total"]
    if sup:
        partes.append(f"{sup} m²")
    if p["ambientes"]:
        partes.append(plural(p["ambientes"], "ambiente", "ambientes"))
    if p["cocheras"]:
        partes.append(plural(p["cocheras"], "cochera", "cocheras"))
    return " · ".join(partes)


def html_tarjeta(p, orden):
    sup = p["sup_cubierta"] or p["sup_total"] or 0
    estado = ""
    if p["estado"] != "disponible":
        estado = f'<span class="tarjeta-estado">{esc(p["estado"])}</span>'
    portada = f"/assets/img/{OPERACIONES[p['operacion']][0]}/{p['id']}/thumbs/01.jpg"
    cant_fotos = f'<span class="tarjeta-fotos">&#128247; {p["fotos"]}</span>' if p.get("fotos") else ""
    return (
        f'          <div class="col-12 col-sm-6 col-md-4 col-lg-3 tarjeta-propiedad" data-zona="{esc(p["zona"])}" '
        f'data-tipo="{esc(p["tipo"])}" data-ambientes="{p["ambientes"] or 0}" data-precio="{p["precio"]}" '
        f'data-superficie="{sup}" data-orden="{orden}">\n'
        f'            <a class="nav-link" href="{url_pagina(p)}" target="_blank" rel="noopener">\n'
        '              <div class="card h-100">\n'
        f'                <div class="cover cover-small" role="img" aria-label="{esc(p["titulo"])}" '
        f'style="background-image:url({portada})">{estado}{cant_fotos}</div>\n'
        '                <div class="card-body">\n'
        f'                  <h5 class="card-title">{esc(p["barrio"])}, {esc(p["partido"])}</h5>\n'
        f'                  <h5 class="card-title2">{esc(precio(p))}</h5>\n'
        f'                  <p class="card-text">{esc(linea_resumen(p))}</p>\n'
        "                </div>\n"
        "              </div>\n"
        "            </a>\n"
        "          </div>\n"
    )


def html_filtros(props, operacion):
    zonas = list(dict.fromkeys(p["zona"] for p in props))
    tipos = sorted(set(p["tipo"] for p in props))

    def opciones(valores, primero):
        return f'<option value="">{primero}</option>' + "".join(
            f'<option value="{esc(v)}">{esc(v)}</option>' for v in valores)

    ambientes = '<option value="">Cualquiera</option>' + "".join(
        f'<option value="{n}">{n}</option>' for n in (1, 2, 3, 4)) + '<option value="5">5 o más</option>'
    moneda, topes = PRECIOS_FILTRO[operacion]
    precios = '<option value="">Cualquiera</option>' + "".join(
        f'<option value="{v}">Hasta {moneda} {numero(v)}</option>' for v in topes)
    ordenes = (
        '<option value="precio-asc">Precio: menor a mayor</option>'
        '<option value="precio-desc">Precio: mayor a menor</option>'
        '<option value="amb-desc">Más ambientes</option>'
        '<option value="amb-asc">Menos ambientes</option>'
        '<option value="sup-desc">Mayor superficie</option>'
    )

    def campo(nombre, etiqueta, opts):
        ancho = "col-12" if nombre == "orden" else "col-6"
        return (
            f'        <div class="form-group {ancho} col-md">\n'
            f'          <label for="f-{nombre}">{etiqueta}</label>\n'
            f'          <select class="form-control" id="f-{nombre}" name="{nombre}">{opts}</select>\n'
            "        </div>\n"
        )

    return (
        '      <form id="filtros" class="filtros" autocomplete="off">\n'
        '        <div class="form-row">\n'
        + campo("zona", "Zona", opciones(zonas, "Todas"))
        + campo("tipo", "Tipo", opciones(tipos, "Todos"))
        + campo("ambientes", "Ambientes", ambientes)
        + campo("precio", "Precio", precios)
        + campo("orden", "Ordenar por", ordenes)
        + "        </div>\n"
        '        <div class="filtros-pie">\n'
        '          <span id="contador" aria-live="polite"></span>\n'
        '          <button type="button" class="btn btn-link js-limpiar">Limpiar filtros</button>\n'
        "        </div>\n"
        "      </form>\n"
    )


def render_listado(operacion, propiedades, base):
    carpeta, _, _, titulo, imagen = OPERACIONES[operacion]
    # Orden inicial (el mismo que trae el filtro por defecto): precio de menor a mayor.
    props = sorted((p for p in propiedades if p["operacion"] == operacion and p["estado"] != "vendida"),
                   key=lambda p: p["precio"])
    con_filtros = bool(props)

    if props:
        tarjetas = "".join(html_tarjeta(p, i) for i, p in enumerate(props, 1))
        cuerpo = (
            (html_filtros(props, operacion) if con_filtros else "")
            + '      <div class="row" id="grilla">\n' + tarjetas + "      </div>\n"
            + ('      <div class="alert alert-info text-center" id="sin-resultados" hidden>'
               "No hay propiedades con esos filtros. "
               '<button type="button" class="btn btn-link p-0 align-baseline js-limpiar">Limpiar filtros</button>'
               "</div>\n" if con_filtros else "")
        )
    else:
        cuerpo = (
            '      <div class="alert alert-danger"><center><strong> Por el momento no contamos con propiedades en '
            "alquiler disponibles. Podés volver a consultar en los próximos días o contactarnos para avisarte "
            "apenas ingrese una nueva opción. </strong></center></div>\n"
        )

    contenido = (
        f'    <section id="{carpeta}">\n'
        '      <div class="container mt-5 mb-5">\n' + cuerpo + "      </div>\n"
        "    </section>"
    )
    hero = (
        f'      <div class="cover d-flex justify-content-end align-items-start p-5 flex-column" '
        f'style="background-image: url({imagen});">\n'
        f"        <h1>{titulo}</h1>\n"
        "      </div>"
    )
    desc = (f"Propiedades en {'venta' if operacion == 'venta' else 'alquiler'} de Agostino Propiedades, "
            "inmobiliaria de Ramos Mejía.")
    salida = pagina(base, dict(
        TITULO=esc(f"{titulo} | Agostino Propiedades"),
        DESCRIPCION=esc(desc),
        URL=f"{DOMINIO}/{carpeta}.html",
        OG_IMAGEN=DOMINIO + imagen,
        HEAD_EXTRA="",
        DENTRO_HEADER=hero,
        DESPUES_HEADER="",
        CONTENIDO=contenido,
        SCRIPTS='    <script src="/assets/js/listado.js" defer></script>' if con_filtros else "",
    ))
    escribir(f"{carpeta}.html", salida)
    return len(props)


# ---------- piezas del Home ----------

def disponibles(propiedades, operacion):
    return [p for p in propiedades if p["operacion"] == operacion and p["estado"] != "vendida"]


def opciones_filtro(props, operacion):
    moneda, topes = PRECIOS_FILTRO[operacion]
    return dict(
        zonas=[[z, z] for z in dict.fromkeys(p["zona"] for p in props)],
        tipos=[[t, t] for t in sorted(set(p["tipo"] for p in props))],
        precios=[[str(v), f"Hasta {moneda} {numero(v)}"] for v in topes],
    )


def html_buscador(propiedades):
    ops = {op: opciones_filtro(disponibles(propiedades, op), op) for op in OPERACIONES if disponibles(propiedades, op)}
    if not ops:
        return ""
    primera = next(iter(ops))

    def select(nombre, etiqueta, opciones):
        opts = "".join(f'<option value="{esc(v)}">{esc(t)}</option>' for v, t in opciones)
        return (f'        <div><label for="b-{nombre}">{etiqueta}</label>'
                f'<select class="form-control" id="b-{nombre}" name="{nombre}">{opts}</select></div>\n')

    d = ops[primera]
    return (
        '    <div class="container">\n'
        f'      <form class="buscador" id="buscador" action="/{OPERACIONES[primera][0]}.html" method="get" '
        f'data-opciones="{esc(json.dumps(ops, ensure_ascii=False))}">\n'
        + select("op", "Operación", [[op, OPERACIONES[op][2]] for op in ops])
        + select("zona", "Zona", [["", "Todas"]] + d["zonas"])
        + select("tipo", "Tipo", [["", "Todos"]] + d["tipos"])
        + select("precio", "Precio", [["", "Cualquiera"]] + d["precios"])
        + '        <button type="submit" class="btn btn-danger">Buscar</button>\n'
        "      </form>\n"
        "    </div>"
    )


def html_destacadas(propiedades):
    # Sin JS se ven 4 repartidas por precio; con JS se eligen 4 al azar en cada visita (assets/js/home.js).
    props = sorted(disponibles(propiedades, "venta"), key=lambda p: p["precio"])
    if not props:
        return ""
    n = len(props)
    idx = sorted(set(round(i * (n - 1) / 3) for i in range(4))) if n > 4 else list(range(n))
    orden = [props[i] for i in idx] + [p for i, p in enumerate(props) if i not in idx]
    tarjetas = "".join(html_tarjeta(p, i) for i, p in enumerate(orden, 1))
    return (
        '    <section id="destacadas">\n'
        '      <div class="container mt-5 pt-4">\n'
        '        <div class="seccion-cabeza"><h2>Propiedades destacadas</h2>'
        '<a href="/ventas.html">Ver todas las propiedades &rarr;</a></div>\n'
        '        <div class="row" id="destacadas-grilla">\n' + tarjetas + "        </div>\n"
        "      </div>\n"
        "    </section>"
    )


def html_opiniones(datos):
    tarjetas = "".join(
        '          <div class="col-12 col-sm-6 col-lg-4 mb-4">\n'
        '            <div class="card h-100 p-4">\n'
        '              <div class="resenas-estrellas mb-3">★★★★★</div>\n'
        f'              <p class="card-text">"{esc(o["texto"])}"</p>\n'
        f'              <p class="resenas-autor">&mdash; {esc(o["nombre"])}</p>\n'
        "            </div>\n"
        "          </div>\n"
        for o in datos["opiniones"]
    )
    url = esc(datos["url"])
    return (
        '    <section id="resenas">\n'
        '      <div class="container mt-5 mb-5">\n'
        '        <div class="text-center mb-4">\n'
        "          <h2>Lo que dicen nuestros clientes</h2>\n"
        f'          <a class="resenas-badge" href="{url}" target="_blank" rel="noopener">\n'
        '            <span class="resenas-estrellas">★★★★★</span>\n'
        f'            <strong>{datos["puntaje"]}</strong> &middot; {datos["cantidad"]} opiniones en Google\n'
        "          </a>\n"
        "        </div>\n"
        '        <div class="row justify-content-center">\n' + tarjetas + "        </div>\n"
        '        <div class="text-center mt-3">\n'
        f'          <a class="btn btn-outline-danger" href="{url}" target="_blank" rel="noopener">Ver todas las opiniones en Google</a>\n'
        "        </div>\n"
        "      </div>\n"
        "    </section>"
    )


# ---------- páginas fijas (Home, Tasaciones, Quiénes somos, Contacto, 404) ----------

def leer_pagina_fija(ruta):
    """Formato del archivo fuente en _build/paginas/:
       ---
       clave: valor      (archivo, url, titulo, descripcion, imagen, script, noindex)
       ---
       <!-- hero -->      (HTML que va dentro del <header>, debajo del menú)
       <!-- contenido --> (HTML del cuerpo de la página)
    """
    with open(ruta, encoding="utf-8") as f:
        texto = f.read()
    _, cabecera, resto = texto.split("---\n", 2)
    meta = {}
    for linea in cabecera.strip().splitlines():
        clave, valor = linea.split(": ", 1)
        meta[clave.strip()] = valor.strip()
    hero, contenido = resto.split("<!-- contenido -->", 1)
    meta["hero"] = hero.replace("<!-- hero -->", "").strip("\n")
    meta["contenido"] = contenido.strip("\n")
    return meta


def render_paginas_fijas(base, propiedades, opiniones):
    carpeta = os.path.join(RAIZ, "_build", "paginas")
    publicas = []
    for nombre in sorted(os.listdir(carpeta)):
        if not nombre.endswith(".html"):
            continue
        m = leer_pagina_fija(os.path.join(carpeta, nombre))
        noindex = m.get("noindex") == "si"
        salida = pagina(base, dict(
            TITULO=esc(m["titulo"]),
            DESCRIPCION=esc(m["descripcion"]),
            URL=DOMINIO + m["url"],
            OG_IMAGEN=DOMINIO + m["imagen"],
            HEAD_EXTRA='    <meta name="robots" content="noindex" />\n' if noindex else "",
            DENTRO_HEADER=m["hero"],
            DESPUES_HEADER="",
            CONTENIDO=m["contenido"].replace("{{BUSCADOR}}", html_buscador(propiedades))
                                    .replace("{{DESTACADAS}}", html_destacadas(propiedades))
                                    .replace("{{OPINIONES}}", html_opiniones(opiniones))
                                    .replace("{{PUNTAJE}}", str(opiniones["puntaje"]))
                                    .replace("{{CANTIDAD}}", str(opiniones["cantidad"])),
            SCRIPTS=f'    <script src="{m["script"]}" defer></script>' if m.get("script") else "",
        ))
        escribir(m["archivo"], salida)
        print(f"OK {m['archivo']}")
        if not noindex:
            publicas.append(m["url"])
    return publicas


def escribir_sitemap_y_robots(urls):
    filas = "".join(f"  <url><loc>{DOMINIO}{u}</loc></url>\n" for u in urls)
    escribir("sitemap.xml",
             '<?xml version="1.0" encoding="UTF-8"?>\n'
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + filas + "</urlset>\n")
    escribir("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {DOMINIO}/sitemap.xml\n")
    print(f"OK sitemap.xml ({len(urls)} páginas) y robots.txt")


def main():
    ruta_json = os.path.join(RAIZ, "data", "propiedades.json")
    with open(ruta_json, encoding="utf-8") as f:
        propiedades = json.load(f)
    with open(os.path.join(RAIZ, "_build", "base.html"), encoding="utf-8") as f:
        base = f.read()
    with open(os.path.join(RAIZ, "data", "opiniones.json"), encoding="utf-8") as f:
        opiniones = json.load(f)
    validar_datos(propiedades)

    cambio = False
    for p in propiedades:
        n = render_detalle(p, base)
        if p.get("fotos") != n:
            print(f"  fotos de {p['id']}: {p.get('fotos')} -> {n}")
            p["fotos"] = n
            cambio = True
        print(f"OK {url_pagina(p).lstrip('/')} ({n} fotos)")

    for operacion in OPERACIONES:
        n = render_listado(operacion, propiedades, base)
        print(f"OK {OPERACIONES[operacion][0]}.html ({n} propiedades)")

    urls = render_paginas_fijas(base, propiedades, opiniones)
    urls += [f"/{OPERACIONES[o][0]}.html" for o in OPERACIONES]
    urls += [url_pagina(p) for p in propiedades if p["estado"] != "vendida"]
    escribir_sitemap_y_robots(sorted(dict.fromkeys(urls), key=lambda u: (u != "/", u)))

    if cambio:
        with open(ruta_json, "w", encoding="utf-8", newline="\n") as f:
            json.dump(propiedades, f, ensure_ascii=False, indent=2)
            f.write("\n")
    print(f"Listo: {len(propiedades)} propiedades.")


if __name__ == "__main__":
    main()
