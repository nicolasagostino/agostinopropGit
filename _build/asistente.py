"""Asistente para cargar y mantener propiedades. Corre solo en tu computadora.

Uso (desde la raíz del repositorio):
    python _build/asistente.py

Abre una página en el navegador donde podés:
- agregar una propiedad (fotos, datos, descripción y características, con ayudas y revisión),
- editar, marcar como reservada o vendida, cambiar el precio o quitar propiedades,
- editar las opiniones de clientes,
- generar las páginas del sitio (equivale a correr build.py).

No se sube a ningún lado ni usa cuentas: al terminar, comiteás y subís como siempre.
Se cierra con Ctrl+C. Requiere Pillow (pip install pillow).
"""
import contextlib
import html
import io
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import traceback
import uuid
import webbrowser
from collections import Counter
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import build  # noqa: E402
import importar_fotos  # noqa: E402
import validacion  # noqa: E402

RAIZ = build.RAIZ
DIR_UI = os.path.join(AQUI, "asistente")
RUTA_PROPIEDADES = os.path.join(RAIZ, "data", "propiedades.json")
RUTA_OPINIONES = os.path.join(RAIZ, "data", "opiniones.json")
TMP = os.path.join(tempfile.gettempdir(), "agostino_asistente")
SUBIDAS = os.path.join(TMP, "subidas")
PAPELERA = os.path.join(TMP, "papelera")
COPIAS = os.path.join(TMP, "copias")

ORDEN_CLAVES = ["id", "operacion", "estado", "titulo", "zona", "direccion", "barrio", "partido", "tipo",
                "moneda", "precio", "expensas", "sup_total", "sup_cubierta", "ambientes", "dormitorios",
                "banos", "cocheras", "antiguedad", "extras", "descripcion", "caracteristicas", "fotos",
                "video", "mapa"]
GRUPOS = ["Características Generales", "Servicios", "Ambientes", "Características", "Comodidades y equipamiento"]
MAX_SUBIDA = 80 * 1024 * 1024

CANDADO = threading.Lock()
ACCIONES = []  # lo que se hizo en esta sesión (para sugerir el mensaje de commit)


class ErrorApi(Exception):
    def __init__(self, mensaje, estado=400, extra=None):
        super().__init__(mensaje)
        self.estado = estado
        self.cuerpo = dict(extra or {}, error=mensaje)


# ---------- archivos de datos ----------

def leer_json(ruta):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def escribir_json(ruta, datos):
    os.makedirs(COPIAS, exist_ok=True)
    if os.path.exists(ruta):
        shutil.copy2(ruta, os.path.join(COPIAS, f"{os.path.basename(ruta)}.{time.strftime('%Y%m%d-%H%M%S')}.bak"))
    temporal = ruta + ".tmp"
    with open(temporal, "w", encoding="utf-8", newline="\n") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(temporal, ruta)


def registrar(texto):
    ACCIONES.append(texto)


def sin_publicar():
    generado = os.path.join(RAIZ, "sitemap.xml")
    if not os.path.exists(generado):
        return True
    return max(os.path.getmtime(RUTA_PROPIEDADES), os.path.getmtime(RUTA_OPINIONES)) > os.path.getmtime(generado) + 3


# ---------- fotos ----------

def carpeta_fotos(operacion, pid):
    if operacion not in build.OPERACIONES:
        raise ErrorApi("Operación inválida.")
    if not re.fullmatch(r"[a-z0-9_]+", pid or ""):
        raise ErrorApi("Identificador inválido.")
    return os.path.join(RAIZ, "assets", "img", build.OPERACIONES[operacion][0], pid)


def fotos_existentes(operacion, pid):
    base = carpeta_fotos(operacion, pid)
    nombres, i = [], 1
    while os.path.exists(os.path.join(base, f"{i:02d}.jpg")):
        nombres.append(f"{i:02d}.jpg")
        i += 1
    return nombres


# ---------- normalización de lo que llega del formulario ----------

def texto(v):
    return v.strip() if isinstance(v, str) else ""


def numero(v):
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if isinstance(v, bool):
        return v
    s = str(v).strip()
    if re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d+)?", s):  # 61.500 -> 61500 (punto de miles)
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    try:
        n = float(s)
    except ValueError:
        return str(v)  # se deja tal cual para que la validación lo marque
    return int(n) if n == int(n) else n


def sin_repetidos(lista):
    return list(dict.fromkeys(lista))


def extraer_mapa(v):
    v = texto(v)
    if "<iframe" in v.lower():
        m = re.search(r'src="([^"]+)"', v)
        v = html.unescape(m.group(1)) if m else ""
    return v or None


def normalizar(d):
    p = {"id": texto(d.get("id")).lower(), "operacion": texto(d.get("operacion")),
         "estado": texto(d.get("estado")) or "disponible"}
    for campo in ("titulo", "zona", "direccion", "barrio", "partido", "tipo", "moneda"):
        p[campo] = texto(d.get(campo))
    p["precio"] = numero(d.get("precio"))
    p["expensas"] = numero(d.get("expensas"))
    for campo in validacion.CAMPOS_NUMERICOS:
        p[campo] = numero(d.get(campo))
    extras = d.get("extras") if isinstance(d.get("extras"), list) else []
    p["extras"] = sin_repetidos([texto(x) for x in extras if texto(x)])
    descripcion = d.get("descripcion") if isinstance(d.get("descripcion"), list) else []
    p["descripcion"] = [texto(x) for x in descripcion if texto(x)]
    car = d.get("caracteristicas") if isinstance(d.get("caracteristicas"), dict) else {}
    p["caracteristicas"] = {}
    for grupo, items in car.items():
        if isinstance(items, list):
            items = sin_repetidos([texto(x) for x in items if texto(x)])
            if items and texto(grupo):
                p["caracteristicas"][texto(grupo)] = items
    p["fotos"] = int(d.get("fotos") or 0) if isinstance(d.get("fotos"), (int, float)) else 0
    p["video"] = d.get("video") or None
    p["mapa"] = extraer_mapa(d.get("mapa"))
    return {k: p[k] for k in ORDEN_CLAVES}


def buscar(props, pid):
    for i, p in enumerate(props):
        if p["id"] == pid:
            return i
    raise ErrorApi("No encontré esa propiedad.", 404)


# ---------- operaciones (API) ----------

def frecuentes(valores, limite=None, minimo=1):
    return [v for v, n in Counter(v for v in valores if v).most_common(limite) if n >= minimo]


def opciones(props):
    return {
        "zonas": frecuentes(p["zona"] for p in props),
        "barrios": frecuentes(p["barrio"] for p in props),
        "partidos": frecuentes(p["partido"] for p in props),
        "tipos": frecuentes(p["tipo"] for p in props),
        "extras": frecuentes((x for p in props for x in p["extras"]), 30),
        "items": {g: frecuentes((x for p in props for x in p["caracteristicas"].get(g, [])), 40, 2) for g in GRUPOS},
    }


def api_estado(consulta, cuerpo):
    props = leer_json(RUTA_PROPIEDADES)
    grupos = GRUPOS + sorted({g for p in props for g in p["caracteristicas"]} - set(GRUPOS))
    return {"propiedades": props, "opiniones": leer_json(RUTA_OPINIONES), "opciones": opciones(props),
            "sinPublicar": sin_publicar(), "grupos": grupos, "acciones": ACCIONES}


def api_fotos(consulta, cuerpo):
    operacion, pid = consulta.get("operacion", [""])[0], consulta.get("id", [""])[0]
    base = carpeta_fotos(operacion, pid)
    carpeta = build.OPERACIONES[operacion][0]
    salida = []
    for nombre in fotos_existentes(operacion, pid):
        miniatura = os.path.join(base, "thumbs", nombre)
        sub = "thumbs/" if os.path.exists(miniatura) else ""
        salida.append({"nombre": nombre, "url": f"/assets/img/{carpeta}/{pid}/{sub}{nombre}?v={int(os.path.getmtime(os.path.join(base, nombre)))}"})
    return {"fotos": salida}


def validar_entrada(cuerpo, props):
    p = normalizar(cuerpo.get("propiedad") or {})
    nueva = bool(cuerpo.get("nueva"))
    otros = [x["id"] for x in props if x["id"] != p["id"]] if not nueva else [x["id"] for x in props]
    n_fotos = cuerpo.get("nFotos")
    errores, avisos = validacion.validar_propiedad(p, otros, n_fotos if isinstance(n_fotos, int) else None)
    return p, errores, avisos


def api_validar(consulta, cuerpo):
    p, errores, avisos = validar_entrada(cuerpo, leer_json(RUTA_PROPIEDADES))
    return {"errores": errores, "avisos": avisos}


def api_tarjeta(consulta, cuerpo):
    p = normalizar(cuerpo.get("propiedad") or {})
    p["fotos"] = int(cuerpo.get("nFotos") or 0)
    try:
        return {"html": build.html_tarjeta(p, 1)}
    except Exception:  # datos todavía incompletos
        return {"html": ""}


def api_guardar(consulta, cuerpo):
    props = leer_json(RUTA_PROPIEDADES)
    nueva = bool(cuerpo.get("nueva"))
    p = normalizar(cuerpo.get("propiedad") or {})
    if nueva and any(x["id"] == p["id"] for x in props):
        raise ErrorApi("Ya existe una propiedad con ese identificador.")
    if not nueva:
        indice = buscar(props, p["id"])
    n_fotos = len(fotos_existentes(p["operacion"], p["id"])) if p["operacion"] in build.OPERACIONES and re.fullmatch(r"[a-z0-9_]+", p["id"]) else 0
    otros = [x["id"] for x in props if x["id"] != p["id"]]
    errores, avisos = validacion.validar_propiedad(p, otros, n_fotos)
    if errores:
        raise ErrorApi("Hay datos para corregir.", 400, {"errores": errores, "avisos": avisos})
    p["fotos"] = n_fotos
    if nueva:
        props.append(p)
        registrar(f"Agregar propiedad: {p['titulo']}")
    else:
        anterior = props[indice]
        props[indice] = p
        registrar(f"Actualizar propiedad: {p['titulo']}")
        if anterior["precio"] != p["precio"]:
            registrar(f"Cambiar precio de {p['id']}: {anterior['precio']} -> {p['precio']}")
    escribir_json(RUTA_PROPIEDADES, props)
    return {"ok": True, "propiedad": p, "avisos": avisos}


def api_rapida(consulta, cuerpo):
    props = leer_json(RUTA_PROPIEDADES)
    indice = buscar(props, cuerpo.get("id"))
    p = props[indice]
    campo, valor = cuerpo.get("campo"), cuerpo.get("valor")
    if campo == "estado":
        if valor not in validacion.ESTADOS:
            raise ErrorApi("Estado inválido.")
        p["estado"] = valor
        registrar(f"Marcar como {valor}: {p['titulo']}")
    elif campo == "precio":
        nuevo = numero(valor)
        if not isinstance(nuevo, (int, float)) or nuevo <= 0:
            raise ErrorApi("El precio tiene que ser un número mayor a 0.")
        registrar(f"Cambiar precio de {p['id']}: {p['precio']} -> {nuevo}")
        p["precio"] = nuevo
    else:
        raise ErrorApi("Campo no permitido.")
    escribir_json(RUTA_PROPIEDADES, props)
    return {"ok": True, "propiedad": p}


def api_quitar(consulta, cuerpo):
    props = leer_json(RUTA_PROPIEDADES)
    indice = buscar(props, cuerpo.get("id"))
    p = props.pop(indice)
    pagina = os.path.join(RAIZ, build.url_pagina(p).lstrip("/").replace("/", os.sep))
    if os.path.exists(pagina):
        os.remove(pagina)
    if cuerpo.get("borrarFotos"):
        base = carpeta_fotos(p["operacion"], p["id"])
        if os.path.isdir(base):
            os.makedirs(PAPELERA, exist_ok=True)
            shutil.move(base, os.path.join(PAPELERA, f"{p['id']}_{time.strftime('%Y%m%d-%H%M%S')}"))
    escribir_json(RUTA_PROPIEDADES, props)
    registrar(f"Quitar propiedad: {p['titulo']}")
    return {"ok": True}


def api_subir(consulta, cuerpo):
    nombre = consulta.get("nombre", ["foto"])[0]
    if not cuerpo:
        raise ErrorApi("La foto llegó vacía.")
    token = uuid.uuid4().hex
    os.makedirs(SUBIDAS, exist_ok=True)
    salida = os.path.join(SUBIDAS, token + ".jpg")
    try:
        ancho, alto = importar_fotos.preparar_foto(io.BytesIO(cuerpo), salida)
    except Exception:
        raise ErrorApi(f"No pude leer la foto «{nombre}». Probá con un archivo JPG o PNG.")
    return {"token": token, "ancho": ancho, "alto": alto}


def api_fotos_aplicar(consulta, cuerpo):
    operacion, pid = cuerpo.get("operacion"), cuerpo.get("id")
    base = carpeta_fotos(operacion, pid)
    orden = cuerpo.get("orden")
    if not isinstance(orden, list) or not orden:
        raise ErrorApi("Falta al menos una foto.")
    preparacion = base + "__nuevo"
    shutil.rmtree(preparacion, ignore_errors=True)
    os.makedirs(preparacion)
    usadas = []
    try:
        for i, item in enumerate(orden, 1):
            destino = os.path.join(preparacion, f"{i:02d}.jpg")
            if "e" in item:
                if not re.fullmatch(r"\d+\.jpg", item["e"]) or not os.path.exists(os.path.join(base, item["e"])):
                    raise ErrorApi("Una de las fotos actuales ya no existe. Recargá la propiedad.")
                shutil.copy2(os.path.join(base, item["e"]), destino)
            else:
                token = str(item.get("u", ""))
                origen = os.path.join(SUBIDAS, token + ".jpg")
                if not re.fullmatch(r"[0-9a-f]{32}", token) or not os.path.exists(origen):
                    raise ErrorApi("Una de las fotos nuevas no se subió bien. Probá de nuevo.")
                shutil.copy2(origen, destino)
                usadas.append(origen)
    except Exception:
        shutil.rmtree(preparacion, ignore_errors=True)
        raise
    os.makedirs(base, exist_ok=True)
    for nombre in os.listdir(base):
        if re.fullmatch(r"\d+\.jpg", nombre):
            os.remove(os.path.join(base, nombre))
    shutil.rmtree(os.path.join(base, "thumbs"), ignore_errors=True)
    for nombre in os.listdir(preparacion):
        shutil.move(os.path.join(preparacion, nombre), os.path.join(base, nombre))
    os.rmdir(preparacion)
    for origen in usadas:
        with contextlib.suppress(OSError):
            os.remove(origen)
    registrar(f"Actualizar fotos de {pid}")
    return {"ok": True, "n": len(orden)}


def api_opiniones(consulta, cuerpo):
    puntaje, cantidad = numero(cuerpo.get("puntaje")), numero(cuerpo.get("cantidad"))
    url = texto(cuerpo.get("url"))
    reseñas = [{"nombre": texto(o.get("nombre")), "texto": texto(o.get("texto"))} for o in (cuerpo.get("opiniones") or [])]
    reseñas = [o for o in reseñas if o["nombre"] or o["texto"]]
    if not isinstance(puntaje, (int, float)) or not 0 <= puntaje <= 5:
        raise ErrorApi("El puntaje tiene que ser un número entre 0 y 5.")
    if not isinstance(cantidad, int) or cantidad < 0:
        raise ErrorApi("La cantidad de opiniones tiene que ser un número entero.")
    if not url.startswith(("http://", "https://")):
        raise ErrorApi("El enlace a Google tiene que empezar con https://")
    if any(not o["nombre"] or not o["texto"] for o in reseñas):
        raise ErrorApi("Cada opinión necesita nombre y texto.")
    escribir_json(RUTA_OPINIONES, {"puntaje": puntaje, "cantidad": cantidad, "url": url, "opiniones": reseñas})
    registrar("Actualizar opiniones de clientes")
    return {"ok": True}


def api_publicar(consulta, cuerpo):
    salida = io.StringIO()
    ok = True
    try:
        with contextlib.redirect_stdout(salida):
            build.main()
    except SystemExit as e:
        ok = e.code in (0, None)
    except Exception:
        ok = False
        salida.write(traceback.format_exc())
    return {"ok": ok, "log": salida.getvalue(), "sinPublicar": sin_publicar()}


def api_commit(consulta, cuerpo):
    acciones = sin_repetidos(ACCIONES)
    if any(a.startswith("Agregar propiedad") for a in acciones):
        acciones = [a for a in acciones if not a.startswith("Actualizar fotos de")]
    if not acciones:
        return {"mensaje": ""}
    titulo = acciones[0] if len(acciones) == 1 else "Actualizar propiedades"
    cuerpo_msg = "" if len(acciones) == 1 else "\n\n" + "\n".join(f"- {a}" for a in acciones)
    return {"mensaje": titulo + cuerpo_msg}


GET = {"estado": api_estado, "fotos": api_fotos, "commit": api_commit}
POST = {"validar": api_validar, "tarjeta": api_tarjeta, "guardar": api_guardar, "rapida": api_rapida,
        "quitar": api_quitar, "subir": api_subir, "fotos_aplicar": api_fotos_aplicar,
        "opiniones": api_opiniones, "publicar": api_publicar}
MUTAN = {"guardar", "rapida", "quitar", "fotos_aplicar", "opiniones", "publicar"}


# ---------- servidor ----------

class Manejador(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=RAIZ, **kwargs)

    def log_message(self, *args):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def translate_path(self, path):
        limpio = urlparse(path).path
        if limpio.startswith("/asistente/") and not limpio.startswith("/asistente/api/"):
            relativo = limpio[len("/asistente/"):] or "index.html"
            ruta = os.path.normpath(os.path.join(DIR_UI, *relativo.split("/")))
            return ruta if ruta.startswith(DIR_UI) else os.path.join(DIR_UI, "no-existe")
        return super().translate_path(path)

    def _responder(self, estado, datos):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(estado)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def _host_valido(self):
        return (self.headers.get("Host") or "").split(":")[0] in ("127.0.0.1", "localhost")

    def _api(self, tabla):
        url = urlparse(self.path)
        nombre = url.path[len("/asistente/api/"):]
        funcion = tabla.get(nombre)
        if not funcion:
            return self._responder(404, {"error": "No existe esa operación."})
        try:
            if tabla is POST:
                largo = int(self.headers.get("Content-Length") or 0)
                if largo > MAX_SUBIDA:
                    raise ErrorApi("El archivo es demasiado grande.", 413)
                crudo = self.rfile.read(largo)
                cuerpo = crudo if nombre == "subir" else (json.loads(crudo.decode("utf-8")) if crudo else {})
            else:
                cuerpo = None
            if nombre in MUTAN:
                with CANDADO:
                    resultado = funcion(parse_qs(url.query), cuerpo)
            else:
                resultado = funcion(parse_qs(url.query), cuerpo)
            self._responder(200, resultado)
        except ErrorApi as e:
            self._responder(e.estado, e.cuerpo)
        except Exception as e:
            traceback.print_exc()
            self._responder(500, {"error": f"Algo falló: {e}"})

    def do_GET(self):
        if not self._host_valido():
            return self.send_error(403)
        ruta = urlparse(self.path).path
        if ruta == "/asistente":
            self.send_response(301)
            self.send_header("Location", "/asistente/")
            self.end_headers()
            return
        if ruta.startswith("/asistente/api/"):
            return self._api(GET)
        return super().do_GET()

    def do_POST(self):
        if not self._host_valido() or self.headers.get("X-Asistente") != "1":
            return self.send_error(403)
        if urlparse(self.path).path.startswith("/asistente/api/"):
            return self._api(POST)
        self.send_error(404)


def main():
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8")
    numeros = [a for a in sys.argv[1:] if a.isdigit()]
    puerto = int(numeros[0]) if numeros else 8765
    servidor = None
    for intento in range(puerto, puerto + 15):
        try:
            servidor = ThreadingHTTPServer(("127.0.0.1", intento), Manejador)
            puerto = intento
            break
        except OSError:
            continue
    if servidor is None:
        sys.exit("No pude abrir el asistente: los puertos están ocupados.")
    url = f"http://127.0.0.1:{puerto}/asistente/"
    print(f"Asistente listo en {url}")
    print("Se abre solo en el navegador. Para cerrarlo, apretá Ctrl+C en esta ventana.")
    if "--sin-navegador" not in sys.argv:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nAsistente cerrado.")
    finally:
        servidor.server_close()


if __name__ == "__main__":
    main()
