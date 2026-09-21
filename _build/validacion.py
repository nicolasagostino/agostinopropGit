"""Reglas de validación de data/propiedades.json.

Las usan el generador (build.py) y el asistente (asistente.py).
Cada problema es un dict {"campo": ..., "mensaje": ...}. Hay dos niveles:
- errores: hay que corregirlos (el generador se detiene).
- avisos: conviene revisarlos, pero no impiden generar el sitio.
"""
import re

ESTADOS = ("disponible", "reservada", "vendida")
OPERACIONES = ("venta", "alquiler")
MONEDAS = ("USD", "ARS")
CAMPOS_NUMERICOS = ("sup_total", "sup_cubierta", "ambientes", "dormitorios", "banos", "cocheras", "antiguedad")
TEXTOS_OBLIGATORIOS = (
    ("titulo", "el título"),
    ("zona", "la zona"),
    ("direccion", "la dirección"),
    ("barrio", "el barrio"),
    ("partido", "el partido"),
    ("tipo", "el tipo de propiedad"),
)


def _es_numero(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _mayusculas(texto):
    letras = [c for c in texto if c.isalpha()]
    return len(letras) >= 12 and sum(c.isupper() for c in letras) / len(letras) > 0.7


def validar_propiedad(p, otros_ids=(), n_fotos=None):
    """Devuelve (errores, avisos). n_fotos=None omite el chequeo de fotos."""
    errores, avisos = [], []

    def error(campo, mensaje):
        errores.append({"campo": campo, "mensaje": mensaje})

    def aviso(campo, mensaje):
        avisos.append({"campo": campo, "mensaje": mensaje})

    pid = p.get("id")
    if not isinstance(pid, str) or not re.fullmatch(r"[a-z0-9_]+", pid or ""):
        error("id", "El identificador solo puede tener minúsculas, números y guion bajo (sin espacios ni tildes).")
    elif pid in otros_ids:
        error("id", f"Ya existe otra propiedad con el identificador «{pid}».")

    if p.get("operacion") not in OPERACIONES:
        error("operacion", "Elegí si es una venta o un alquiler.")
    if p.get("estado") not in ESTADOS:
        error("estado", "El estado tiene que ser disponible, reservada o vendida.")
    if p.get("moneda") not in MONEDAS:
        error("moneda", "Elegí la moneda (USD o ARS).")

    for campo, nombre in TEXTOS_OBLIGATORIOS:
        valor = p.get(campo)
        if not isinstance(valor, str) or not valor.strip():
            error(campo, f"Falta completar {nombre}.")

    precio = p.get("precio")
    if not _es_numero(precio) or precio <= 0:
        error("precio", "El precio tiene que ser un número mayor a 0 (sin puntos ni símbolos).")
    else:
        if p.get("operacion") == "venta" and p.get("moneda") == "USD" and not 5000 <= precio <= 5_000_000:
            aviso("precio", "El precio en dólares parece fuera de lo habitual, revisalo.")
        if p.get("operacion") == "alquiler" and p.get("moneda") == "ARS" and precio < 50_000:
            aviso("precio", "El alquiler en pesos parece muy bajo, ¿está bien?")

    expensas = p.get("expensas")
    if expensas is not None and (not _es_numero(expensas) or expensas < 0):
        error("expensas", "Las expensas tienen que ser un número (o dejarse vacías).")

    for campo in CAMPOS_NUMERICOS:
        valor = p.get(campo)
        if valor is not None and (not _es_numero(valor) or valor < 0):
            error(campo, "Tiene que ser un número (o dejarse vacío).")
    if _es_numero(p.get("sup_total")) and _es_numero(p.get("sup_cubierta")) and p["sup_cubierta"] > p["sup_total"]:
        aviso("sup_cubierta", "La superficie cubierta es mayor que la total, ¿está bien?")
    if not _es_numero(p.get("ambientes")):
        aviso("ambientes", "Falta la cantidad de ambientes (se usa en los filtros del listado).")
    if not p.get("sup_total") and not p.get("sup_cubierta"):
        aviso("sup_total", "No hay ninguna superficie cargada.")

    extras = p.get("extras")
    if not isinstance(extras, list) or not all(isinstance(x, str) for x in extras):
        error("extras", "Las etiquetas tienen que ser una lista de textos.")

    descripcion = p.get("descripcion")
    if not isinstance(descripcion, list) or not all(isinstance(x, str) for x in descripcion):
        error("descripcion", "La descripción tiene que ser una lista de párrafos.")
    elif not any(x.strip() for x in descripcion):
        aviso("descripcion", "Falta la descripción de la propiedad.")
    elif any(_mayusculas(x) for x in descripcion):
        aviso("descripcion", "Hay párrafos escritos todo en mayúsculas; se leen mejor en minúscula normal.")

    if isinstance(p.get("titulo"), str) and _mayusculas(p["titulo"]):
        aviso("titulo", "El título está todo en mayúsculas.")

    caracteristicas = p.get("caracteristicas")
    if not isinstance(caracteristicas, dict) or not all(
            isinstance(k, str) and isinstance(v, list) and all(isinstance(x, str) for x in v)
            for k, v in caracteristicas.items()):
        error("caracteristicas", "Las características tienen que ser grupos con listas de textos.")

    mapa = p.get("mapa")
    if not mapa:
        aviso("mapa", "No hay mapa cargado (la página de la propiedad no mostrará la ubicación).")
    elif not str(mapa).startswith("https://www.google.com/maps/"):
        aviso("mapa", "El mapa no parece un enlace de «Insertar un mapa» de Google Maps.")

    if n_fotos is not None:
        if n_fotos == 0 and p.get("estado") != "vendida":
            error("fotos", "Falta al menos una foto (la primera es la portada).")
        elif n_fotos < 3 and p.get("estado") != "vendida":
            aviso("fotos", "Hay muy pocas fotos; conviene cargar más.")

    return errores, avisos


def validar_todas(propiedades, contar_fotos):
    """contar_fotos(p) -> cantidad de fotos de la propiedad. Devuelve (errores, avisos) con el id en cada problema."""
    errores, avisos = [], []
    ids = [p.get("id") for p in propiedades]
    for i, p in enumerate(propiedades):
        otros = [x for j, x in enumerate(ids) if j != i]
        e, a = validar_propiedad(p, otros, contar_fotos(p))
        errores += [dict(x, id=p.get("id")) for x in e]
        avisos += [dict(x, id=p.get("id")) for x in a]
    return errores, avisos
