"""Prepara las fotos de una propiedad para el sitio.

Toma una carpeta con fotos "crudas" (del celular o la cámara), las achica, las numera
como 01.jpg, 02.jpg... y las deja en assets/img/<ventas|alquileres>/<id>/.

Uso (desde la raíz del repositorio):
    python _build/importar_fotos.py <carpeta_con_fotos> <venta|alquiler> <id>
    python _build/importar_fotos.py "C:\\Fotos\\casa_paso" venta paso
    python _build/importar_fotos.py "C:\\Fotos\\mas_fotos" venta paso --agregar

Opciones:
    --agregar     suma las fotos a las que ya hay (sigue la numeración)
    --reemplazar  borra las fotos actuales de esa propiedad y carga las nuevas
    --por-fecha   ordena por fecha de la foto en vez de por nombre de archivo
    --lado N      lado mayor máximo en píxeles (por defecto 2000)

- El id es el nombre corto de la propiedad: minúsculas, números y guion bajo (ej: gonzalez_castillo).
- La primera foto (01.jpg) es la portada.
- Se corrige la rotación y se BORRAN los datos ocultos de la foto (incluida la ubicación GPS).
- Después de importar: cargá la propiedad en data/propiedades.json y corré  python _build/build.py

Requiere Pillow (pip install pillow). Para fotos .heic de iPhone: pip install pillow-heif
"""
import argparse
import os
import re
import shutil
import sys

from PIL import Image, ImageOps

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIC = True
except ImportError:
    HEIC = False

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARPETAS = {"venta": "ventas", "alquiler": "alquileres"}
EXTENSIONES = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}


def preparar_foto(fuente, salida, lado=2000):
    """Achica la foto (sin agrandarla), corrige la rotación, borra los datos ocultos y la guarda como JPEG.
    fuente puede ser una ruta o un archivo en memoria. Devuelve (ancho, alto)."""
    with Image.open(fuente) as im:
        img = ImageOps.exif_transpose(im).convert("RGB")
    img.thumbnail((lado, lado), Image.LANCZOS)
    img.save(salida, "JPEG", quality=82, optimize=True, progressive=True)
    return img.size


def clave_natural(nombre):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", nombre)]


def fecha_foto(ruta):
    try:
        with Image.open(ruta) as im:
            valor = im.getexif().get_ifd(0x8769).get(0x9003)  # DateTimeOriginal
        if valor:
            return valor
    except Exception:
        pass
    return None


def listar_origen(origen, por_fecha):
    archivos = [f for f in os.listdir(origen) if os.path.splitext(f)[1].lower() in EXTENSIONES]
    if not HEIC:
        heic = [f for f in archivos if f.lower().endswith((".heic", ".heif"))]
        if heic:
            sys.exit(f"Hay {len(heic)} fotos .heic (iPhone) y falta el soporte. Instalalo con:  pip install pillow-heif")
    if por_fecha:
        archivos.sort(key=lambda f: (fecha_foto(os.path.join(origen, f)) or "9999", clave_natural(f)))
    else:
        archivos.sort(key=clave_natural)
    return [os.path.join(origen, f) for f in archivos]


def fotos_actuales(destino):
    if not os.path.isdir(destino):
        return []
    return sorted(f for f in os.listdir(destino) if re.fullmatch(r"\d+\.jpg", f))


def main():
    ap = argparse.ArgumentParser(description="Prepara las fotos de una propiedad.")
    ap.add_argument("origen")
    ap.add_argument("operacion", choices=list(CARPETAS))
    ap.add_argument("id")
    grupo = ap.add_mutually_exclusive_group()
    grupo.add_argument("--agregar", action="store_true")
    grupo.add_argument("--reemplazar", action="store_true")
    ap.add_argument("--por-fecha", action="store_true")
    ap.add_argument("--lado", type=int, default=2000)
    a = ap.parse_args()

    if not re.fullmatch(r"[a-z0-9_]+", a.id):
        sys.exit("El id solo puede tener minúsculas, números y guion bajo (sin espacios ni tildes). Ej: gonzalez_castillo")
    if not os.path.isdir(a.origen):
        sys.exit(f"No existe la carpeta: {a.origen}")

    fotos = listar_origen(a.origen, a.por_fecha)
    if not fotos:
        sys.exit("No encontré fotos en esa carpeta (busco .jpg, .jpeg, .png, .webp y .heic).")

    destino = os.path.join(RAIZ, "assets", "img", CARPETAS[a.operacion], a.id)
    existentes = fotos_actuales(destino)
    if existentes and not (a.agregar or a.reemplazar):
        sys.exit(f"{a.id} ya tiene {len(existentes)} fotos. Usá --agregar para sumar más o --reemplazar para cambiarlas.")
    if existentes and a.reemplazar:
        for f in existentes:
            os.remove(os.path.join(destino, f))
        shutil.rmtree(os.path.join(destino, "thumbs"), ignore_errors=True)
        existentes = []

    os.makedirs(destino, exist_ok=True)
    numero = len(existentes) + 1
    peso_antes = peso_despues = 0
    for ruta in fotos:
        salida = os.path.join(destino, f"{numero:02d}.jpg")
        ancho, alto = preparar_foto(ruta, salida, a.lado)
        peso_antes += os.path.getsize(ruta)
        peso_despues += os.path.getsize(salida)
        print(f"  {os.path.basename(ruta)} -> {numero:02d}.jpg ({ancho}x{alto})")
        numero += 1

    total = numero - 1
    print(f"\nListo: {len(fotos)} fotos importadas en assets/img/{CARPETAS[a.operacion]}/{a.id}/ (ahora hay {total}).")
    print(f"Peso: {peso_antes / 1e6:.1f} MB -> {peso_despues / 1e6:.1f} MB")
    print("Siguiente paso: cargá la propiedad en data/propiedades.json y corré  python _build/build.py")


if __name__ == "__main__":
    main()
