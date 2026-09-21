# Agostino Propiedades

Sitio web de Agostino Propiedades (https://agostinoprop.com.ar), publicado con GitHub Pages.
Es un sitio estático: no hay servidor ni base de datos. Las páginas se generan con un script a partir de un archivo de datos.

## Cómo está armado

| Qué | Dónde |
| --- | --- |
| Datos de todas las propiedades (venta y alquiler) | `data/propiedades.json` |
| Fotos de cada propiedad | `assets/img/ventas/<id>/` y `assets/img/alquileres/<id>/` |
| Contenido de Home, Tasaciones, Quiénes somos, Contacto y 404 | `_build/paginas/` |
| Menú, pie de página y estructura común de las páginas | `_build/base.html` |
| Generador de páginas | `_build/build.py` |
| Preparar fotos nuevas | `_build/importar_fotos.py` |
| Estilos | `style.css` |
| JS de la galería y de los filtros | `assets/js/` |

**Las páginas HTML de la raíz y de `ventas/` y `alquileres/` son generadas: no se editan a mano.** Cada una trae un comentario arriba que lo recuerda. Cualquier cambio que se haga ahí se pierde la próxima vez que se corra el generador.

## Requisitos

Python 3 y Pillow: `pip install pillow` (para fotos `.heic` de iPhone, además `pip install pillow-heif`).

## Tareas comunes

### Agregar una propiedad

1. **Fotos.** Poné las fotos originales en una carpeta cualquiera (fuera del repositorio) y ejecutá:

   ```
   python _build/importar_fotos.py "C:\Fotos\casa_nueva" venta melo2
   ```

   `venta` o `alquiler`, y un id corto: minúsculas, números y guion bajo, sin espacios ni tildes. Las fotos se achican, se numeran (`01.jpg` es la portada) y se les borra la ubicación GPS. Con `--agregar` se suman a una propiedad que ya tiene fotos; con `--reemplazar` se cambian todas.

2. **Datos.** Copiá un registro de `data/propiedades.json`, cambiale el `id` (el mismo del paso 1) y completá los datos.

3. **Generar.** `python _build/build.py`

4. **Revisar.** Servir el sitio en local y abrirlo en el navegador (abrir los archivos directamente no funciona, las rutas son del sitio):

   ```
   python -m http.server 8000
   ```

   Después abrir http://localhost:8000/ventas.html

5. **Publicar.** Comitear y subir. GitHub Pages actualiza el sitio en un par de minutos.

### Cambiar un dato (precio, texto, etc.)

Editar la propiedad en `data/propiedades.json`, correr `python _build/build.py` y comitear.

### Marcar una propiedad como reservada o vendida

Cambiar `estado` a `"reservada"` (aparece con una etiqueta) o `"vendida"` (deja de aparecer en el listado y en el sitemap, pero su página sigue existiendo para los links ya compartidos).

### Quitar una propiedad

Borrar su registro del JSON, su página (`ventas/ven_<id>.html` o `alquileres/alq_<id>.html`) y su carpeta de fotos. El generador no borra páginas viejas.

### Editar Home, Tasaciones, Quiénes somos o Contacto

Editar el archivo con ese nombre en `_build/paginas/` y correr el generador. Cada archivo empieza con el título y la descripción que ve Google, y después tiene el bloque `<!-- hero -->` (la cabecera con la imagen) y el bloque `<!-- contenido -->`.

### Cambiar el menú, el pie de página o el `<head>`

Editar `_build/base.html` y correr el generador: se actualizan todas las páginas.

## Campos de `data/propiedades.json`

| Campo | Valor |
| --- | --- |
| `id` | Nombre corto, igual al de la carpeta de fotos |
| `operacion` | `"venta"` o `"alquiler"` |
| `estado` | `"disponible"`, `"reservada"` o `"vendida"` |
| `titulo` | Título de la publicación |
| `zona` | Zona para el filtro del listado (ej. `"Ramos Mejía"`) |
| `direccion`, `barrio`, `partido` | Se muestran como "dirección, barrio, partido" |
| `tipo` | `"PH"`, `"Casa"`, `"Departamento"`, `"Dúplex"`, `"Terreno"`... |
| `moneda`, `precio` | `"USD"` o `"ARS"`, y el número sin puntos |
| `expensas` | Número en pesos, o `null` |
| `sup_total`, `sup_cubierta` | m², o `null` |
| `ambientes`, `dormitorios`, `banos`, `cocheras`, `antiguedad` | Números, o `null` si no se sabe |
| `extras` | Lista de etiquetas cortas (ej. `["Frente", "Luminoso"]`) |
| `descripcion` | Lista de párrafos |
| `caracteristicas` | Grupos de características: `{ "Servicios": ["Gas natural", "Luz"] }` |
| `fotos` | Lo completa solo el generador |
| `video` | Sin uso por ahora, dejar en `null` |
| `mapa` | Link de "insertar mapa" de Google Maps |

## Otras cosas a saber

- **Formulario de contacto:** usa [Web3Forms](https://web3forms.com) y los mensajes llegan a agostinoprop@gmail.com. La clave está en `_build/paginas/contacto.html`.
- **Propiedades destacadas del Home:** se muestran 4 elegidas al azar en cada visita, entre las propiedades en venta disponibles (`assets/js/home.js`). No hace falta marcar ninguna.
- **Buscador del Home:** lleva a Ventas o Alquileres con los filtros ya aplicados; sus opciones se generan solas a partir del JSON.
- **Aviso COTI:** se agrega solo al final de todas las propiedades en venta (texto fijo en `_build/build.py`).
- **Rangos del filtro de precio:** están en `PRECIOS_FILTRO` de `_build/build.py`; conviene ajustarlos si cambian los precios.
- **Dominio:** el archivo `CNAME` apunta a `agostinoprop.com.ar`.
