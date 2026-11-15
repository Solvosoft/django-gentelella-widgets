# djeditor — Editor visual de vistas/formularios que genera código djgentelella

> El código del editor vivirá en un repo aparte, `../djgentelella-editor`. El
> motor de flujos (§6d) se implementa en este repo, dentro de djgentelella.

## Estado (repo djgentelella-editor)

| Fase | Estado |
|---|---|
| F0 Andamiaje y guardas | ✅ hecho |
| F1 Introspección + ERD + `gteditor_graph` | ✅ hecho |
| F2 Núcleo del codegen + `gteditor_generate` + preview de solo lectura | ✅ hecho: `form` y `object_management` (más `page`/`row`/`col`/`html`) |
| F3 Editor de página | ✅ hecho: canvas con SortableJS, panel de propiedades guiado por `props_schema` (pistas `x-widget`), editor de forms, preview en iframe con widgets reales, pestaña Código con diff y aplicación por archivo, JSON, deshacer/rehacer |
| F4 Más componentes | ✅ hecho: `chart` (bar/horizontal_bar/line/pie/doughnut; count/sum/avg/min/max; agrupación por campo, FK, choices o fecha por día/mes/año), `stat`, `crud_classic`, `inline_object_management` sobre páginas con `meta.parent`, `row_links` y `assets` CSS/JS. Los lookups automáticos ya venían de F2 |
| F4b Menú, ayuda, notificaciones | ✅ hecho: `meta.menu` (entrada en sidebar o top bar con grupos padre y permisos de la página), pestaña Menu, ayuda por campo en `forms.<key>.help` con el widget de ayuda en el footer, `notify` en las tablas CRUD (email vía async_notification con plantilla, contexto y `ready()`; aviso in-app), todo sembrado por una data migration con hash |
| F5a Motor de flujos (djgentelella) | ✅ hecho: `djgentelella/flows/` (`Flow`, `Transition`; acciones `SetField`, `Assign`, `Notify`, `SendEmail`, `CallFunction`), `FlowInstance`/`FlowTransitionLog` + migración 0021, páginas de bandeja, detalle y transición, `{% flow_status %}`, `gtflows` autodescubierto, docs y demo |
| F5b Editor de flujos | ✅ hecho: diseños `"kind": "flow"` (`schema_flow_v1.json`), diseñador con diagrama de estados, generación de `Flow` + forms + registro vía `gtflows.py`, grupos y plantillas de email sembrados, `row_links` a `flow:<slug>` |
| F6 Integración | ✅ hecho: panel inyectado por middleware (URL name, vista, abrir el diseño o crear uno prellenado), importación inversa de GTForm/CRUDView (`gteditor_import`, `api/import/`, formulario en la portada), plantillas del codegen sobrescribibles desde `DIRS` del proyecto (con test), cambio de ancho de columnas arrastrando en el canvas |

Diferencias con lo planeado:
- El formato real de `forms` es `{model, fields: [...], render, grid, widgets: {campo: widget}}`.
  Se usa en `testapp/gtdesign/product_admin.json`.
- El validador JSON Schema es propio (`gteditor/jsonschema.py`), sin dependencias.
- El formateo no corre ruff. Las plantillas, con un loader estilo `trim_blocks`,
  ya producen código final. Que el resultado sea determinista, compile y quepa
  en 88 columnas lo verifican los tests golden.
- Licencia del código generado (decidido, opción 3): las plantillas del codegen
  son 0BSD, y los tres módulos que emiten fragmentos son
  `GPL-2.0-or-later OR 0BSD`. El resto del editor sigue siendo GPL-2.0-or-later.
  Ver `THIRD_PARTY_LICENSES.md`.
- F3: el diff se muestra con un `<pre>` coloreado propio, no con CodeMirror,
  que exigiría un bundle ESM. Tampoco hay borrador en localStorage: se avisa
  con `beforeunload`, y guardar detecta conflictos por hash.
- F4: `stat` no usa `djgentelella/elements.py`, porque esas clases arman el HTML
  sin escapar. Genera el markup `tile-stats` en una plantilla, que sí escapa, y
  el valor lo calcula la vista (`get_stats()`, sobrescribible).
- F4b: el menú se diseña por página (`meta.menu`), no con un árbol completo
  por app en `_menu.json`. La pestaña Menu muestra el árbol actual de la base
  como referencia. Tampoco se crean clases nuevas de widgets de menú o footer;
  solo se agrega el widget de ayuda existente. Quitar una entrada del diseño no
  borra la fila: las migraciones semilla solo agregan o actualizan.
- F6: no se usó Gridstack. Las columnas de la grilla Bootstrap se redimensionan
  arrastrando su borde en el canvas, sin otra dependencia. Gridstack (posiciones
  x/y libres) no encaja con `row`/`col` ni con el `grid_representation` que
  genera el editor.
- El usuario extiende en `gtcustom/<slug>.py`, un módulo propio creado una sola
  vez, en lugar de hacerlo en los `forms.py`/`api.py` de la app.

## Contexto

Construir una app en djgentelella hoy implica escribir a mano mucho boilerplate
repetitivo. Para una sola página CRUD estilo "object management"
(`demo/demoapp/object_management/`) se necesitan: GTForm + `Meta.widgets`,
ModelSerializer + TableSerializer + Create/Update serializers + FilterSet, un
`BaseObjectManagement`, el registro en el router, una vista, una plantilla con 3
modales y la config JS de `ObjectCRUD`, lookups `gtselects` para cada FK/M2M,
`gtcharts`, un `MenuItem` y permisos.

El objetivo es un **editor visual de desarrollo** con tres funciones:
- ver los modelos y sus relaciones (como `django-model-visualizer`);
- acomodar componentes djgentelella en una página;
- **generar código Python/plantillas normales** que la app usa sin depender del editor.

Como el editor expone el esquema de la base de datos y escribe archivos, **no debe
llegar nunca a producción**.

### Decisiones tomadas

| Tema | Decisión |
|---|---|
| Distribución | Paquete pip propio en un **repo aparte, `../djgentelella-editor`** (módulo `gteditor`). Se instala solo en requirements de desarrollo. |
| Salida | Muestra el código, luego un diff contra los archivos de la app, y **escribe solo al confirmar**. También se puede exportar como zip. |
| Runtime | **Solo generación.** El JSON de diseño es la fuente de verdad del editor. En producción corre únicamente el código generado. |
| UI | **App independiente** a pantalla completa (`/__gteditor__/`). Además, un **panel flotante** inyectado en las páginas de la app que abre esa página en el editor. |
| Flujos | El **motor de flujos vive en djgentelella** (`djgentelella/flows/`, es código de producción). El editor solo arma la definición y el código que ese motor necesita. |
| Menú | El árbol de `MenuItem` diseñado se materializa como una **data migration idempotente**. |

## Investigación: soluciones existentes y qué tomar de cada una

| Proyecto | Enfoque | Qué tomamos |
|---|---|---|
| django-model-visualizer (MIT) | `apps.get_models()` → JSON en `/viz/api/graph/`; SVG en JS plano con tarjetas arrastrables | Separar un servicio de introspección (JSON) del renderer JS. Usar ese JSON como paleta de modelos. |
| django-extensions `graph_models` | Graphviz estático | Filtros include/exclude por app y modelo |
| django-schema-graph | Página interactiva, oculta si no hay DEBUG (`access_permitted()`) | El patrón de control de acceso |
| django-formidable / django-fobi | Formulario como JSON, interpretado en runtime; un plugin por tipo de elemento | La forma del JSON (campos con type, label y validaciones) y un **registro de plugins** por componente |
| Viewflow / material | Layout como DSL en Python (`Row`, `Fieldset`) | Prueba de que el layout puede vivir como Python plano; nosotros ya tenemos `GTForm.grid_representation` |
| Wagtail StreamField | Árbol JSON `{type, value, id}`; cada tipo de bloque es una clase Python | Usar el mismo modelo para el árbol de componentes |
| Baserow, NocoDB, Appsmith, Budibase, Form.io | Definición JSON interpretada en runtime | Ninguno genera código. **Un generador de código es un hueco real en el ecosistema Django.** |
| django-baker, drf-generators, django-hogwarts, django-app-gen | Plantillas → archivos | Que el proyecto pueda sobrescribir las plantillas del generador (estilo `templates/django_baker/`) |
| django-debug-toolbar, django-silk | `SHOW_TOOLBAR_CALLBACK` (DEBUG + `INTERNAL_IPS`), inyección por middleware antes de `</body>`, exigir superusuario | Las guardas y la inyección del panel |

### Política de licencias: solo compatibles con GPL

djgentelella es **GPL-2.0-or-later** (`LICENSE.txt`, `pyproject.toml`).
`djgentelella-editor` usará la **misma licencia**.

Toda dependencia, Python o JS, empaquetada o vendorizada, tiene que tener una
licencia compatible con GPL-2.0-or-later:

| Estado | Licencias |
|---|---|
| ✅ Aceptadas | MIT/Expat, BSD-2/3, ISC, Zlib, PSF-2, LGPL-2.1+/3, GPL-2.0+/3, MPL-2.0 (salvo si declara "Incompatible With Secondary Licenses") |
| ⚠️ Con cuidado | Apache-2.0 solo es compatible con GPLv3. Como el proyecto es "or-later" la combinación es posible, pero se evita si hay alternativa |
| ❌ Prohibidas | AGPL, EPL-1.0/2.0 sin secondary license, licencias comerciales o "open core" (partes PRO), SSPL, CC-BY-NC, cualquier licencia sin texto |

Cómo se controla:
- `THIRD_PARTY_LICENSES.md` en el repo del editor, con nombre, versión, licencia
  y URL de cada librería.
- Las librerías JS se vendorizan con su archivo LICENSE.
- Un test o paso de CI con `pip-licenses` (MIT) falla si aparece una licencia
  que no está en la lista permitida.

**Código generado.** Las plantillas del codegen terminan copiadas dentro del
código del usuario. Se propone agregar una **excepción explícita de salida**,
como la de Bison/GCC: "el código emitido por el generador puede usarse bajo
cualquier licencia". Así el editor no impone GPL sobre las apps generadas. Se
decide al crear el repo.

### Librerías JS elegidas (todas MIT, sin jQuery obligatorio)

Las licencias están verificadas a nivel de proyecto. Al fijar cada versión hay
que revisar el LICENSE exacto y registrarlo en `THIRD_PARTY_LICENSES.md`.

- **SortableJS (MIT):** canvas anidado de filas, columnas y componentes. Encaja
  directo con la grilla Bootstrap y con `grid_representation`.
- **Gridstack.js (MIT):** solo para páginas tipo dashboard (charts y stats), en
  una fase posterior.
- **Cytoscape.js + cytoscape-dagre + dagre (MIT):** el diagrama ER y el de flujos,
  con layout automático para esquemas grandes. La alternativa liviana es Drawflow
  (MIT).
- **CodeMirror 6 (MIT, incluido `@codemirror/merge`):** vista previa del código,
  el diff y los editores de CSS/JS custom.
- Ya incluidas en djgentelella y reusables: TinyMCE (GPL-2.0+ desde la v7),
  jQuery, Bootstrap, Select2 y DataTables (MIT).

Descartadas:
- **GrapesJS (BSD):** demasiado genérico; produce HTML, no Django.
- **SurveyJS Creator:** comercial ❌.
- **Form.io:** partes premium comerciales ❌.
- **JointJS+** y **jsPlumb Toolkit:** comerciales ❌.
- **elkjs:** EPL-2.0 ❌.
- **Viewflow:** AGPL ❌.
- **formBuilder:** sin columnas.
- **React Flow:** exige React.

### Dependencias Python del editor

- **Ninguna obligatoria** además de djgentelella y Django.
- Para editar archivos existentes se usa el **`ast` de la stdlib** (PSF), en vez
  de libcst. libcst arrastra componentes Apache-2.0 en su parte Rust. Ver §6.5.
- **ruff (MIT)** como extra opcional `[format]`. Se invoca como proceso externo
  para formatear.
- **pip-licenses (MIT)** solo en test/CI.

## Arquitectura

```
../djgentelella-editor/
  pyproject.toml          # GPL-2.0-or-later; deps: djgentelella ; extra [format]: ruff (sin Jinja2 ni libcst)
  THIRD_PARTY_LICENSES.md
  gteditor/
    apps.py  checks.py  guards.py  settings.py  urls.py  middleware.py
    introspection/        # modelos, campos, relaciones, permisos, url names, lookups existentes
    design/               # JSON Schema versionado, carga/validación, almacenamiento en archivos
    components/           # registro de componentes (spec + props + preview + generador)
    mapping.py            # tabla campo-de-modelo → widget / serializer field (default + alternativas)
    codegen/              # IR, Engine de Django + tags gtcodegen, merge con ast, ruff, ChangeSet/diff, escritura
    views/                # API del editor (DRF) + vistas de páginas y preview
    templates/gteditor/   # shell del editor, preview, plantillas del codegen (sobrescribibles)
    static/gteditor/      # bundle propio; NUNCA en createbasejs ni en pylp
    management/commands/  # gteditor_generate, gteditor_graph
  testproject/            # proyecto Django de pruebas (o demo de djgentelella instalado editable)
  plans/
```

### 1. Garantía de que no llega a producción (defensa en capas)

1. **Paquete separado.** Si no está en el requirements de prod, el código ni existe.
   No se toca el wheel de djgentelella.
2. **`AppConfig.ready()`** lanza `ImproperlyConfigured` si `DEBUG=False`. No habrá
   setting para saltarse esto.
3. **System check** `gteditor.E001` si está en `INSTALLED_APPS` sin DEBUG. También
   un warning si `ALLOWED_HOSTS` contiene algo que no sea local.
4. **`gteditor.urls`** devuelve `[]` si no se cumple la guarda. El proyecto lo
   incluye condicionalmente, igual que se recomienda con debug-toolbar.
5. **Todas las vistas y la API** exigen `GTEDITOR_SHOW_CALLBACK`. Por defecto:
   `DEBUG and REMOTE_ADDR in INTERNAL_IPS and user.is_superuser`. CSRF siempre activo.
6. **Escritura acotada.** Solo dentro de `BASE_DIR`, solo en las apps listadas en
   `GTEDITOR_WRITABLE_APPS`, sin symlinks fuera del árbol, y con un backup
   (`.gteditor-bak/`) antes de sobrescribir.
7. **Solo esquema, no datos.** La introspección expone `_meta`, nunca filas. Los
   previews de charts y tablas usan **datos de ejemplo** por defecto; con datos
   reales solo si se marca explícitamente "usar datos locales".
8. **El código generado no importa nada de `gteditor`.** Lo verifica un test de los
   golden files.

### 2. Introspección (`gteditor/introspection/`)

Endpoint `GET /__gteditor__/api/schema/?apps=` que devuelve apps → modelos →
campos. Para cada campo:
- name, tipo, null/blank, choices, max_length, default y help_text;
- relaciones: FK, O2O y M2M con su modelo destino, related_name e inversas;
- `Meta`: verbose names, ordering y permisos (los default y los custom);
- si el modelo es `TreeNode` (habilita `TreeSelect`) y si usa `DeletedWithTrash`.

También devuelve lo que ya existe en el proyecto, para poder reusarlo en vez de
duplicarlo:
- url names (resolver);
- basenames registrados en `djgentelella.groute.routes` (gtselects y gtcharts);
- los `MenuItem`.

Reuso: tomar como base `FIELD_TYPE_MAP`, de
`djgentelella/async_notification/introspection.py`. Se copia y extiende, porque
importarlo exige tener instalada esa app. Usar `apps.get_models()` igual que el
visualizer. El comando `gteditor_graph` exporta el grafo a JSON o a mermaid.

### 3. Documento de diseño (JSON versionado, en el repo de la app)

Se guarda en `<app>/gtdesign/<slug>.json` y se versiona en git, así que se revisa
en PR. No usa tablas ni migraciones del editor. Forma:

```json
{
  "schema_version": 1, "app": "inventory", "slug": "product_admin", "kind": "page",
  "meta": {"title": "Productos", "url": "products/", "url_name": "product_admin",
           "permissions": {"view": ["inventory.view_product"]},
           "menu": {"parent": "Inventario", "category": "sidebar", "icon": "fa fa-box"}},
  "assets": {"css": "static/inventory/gtdesign/product_admin.css",
             "js":  "static/inventory/gtdesign/product_admin.js"},
  "root": {"type": "page", "id": "n1", "children": [
    {"type": "row", "id": "n2", "children": [
      {"type": "col", "id": "n3", "props": {"width": 8}, "children": [
        {"type": "object_management", "id": "n4",
         "props": {"model": "inventory.Product", "list_fields": ["name","price","category"],
                   "search_fields": ["name"], "form": "n5",
                   "perms": {"create": ["inventory.add_product"]}}}]},
      {"type": "col", "id": "n6", "props": {"width": 4}, "children": [
        {"type": "chart", "id": "n7", "props": {"chart": "pie", "model": "inventory.Product",
         "group_by": "category__name", "aggregate": "count"}}]}]}]},
  "forms": {"n5": {"model": "inventory.Product", "render": "as_grid",
    "grid": [[["name"],["price"]],[["category"]]],
    "fields": {"category": {"widget": "AutocompleteSelect", "lookup": "auto"},
               "description": {"widget": "EditorTinymce"}}}}
}
```

- Los ids de nodo son estables. Los usan los marcadores del código y el panel
  inyectado.
- Hay un JSON Schema publicado y la validación se hace en el servidor.
- La migración entre `schema_version` se hace en Python (`design/migrations.py`).

### 4. Registro de componentes (estilo Wagtail blocks / fobi plugins)

Cada componente es una clase `ComponentSpec` con:
- `type`, label e icono para la paleta;
- `props_schema`: JSON Schema que alimenta el panel de propiedades;
- `accepts`: qué se le puede soltar encima (un modelo, un campo, otros componentes);
- `render_preview(node, ctx)`: HTML del widget **djgentelella real**;
- `contribute(node, ir)`: lo que aporta al IR del generador.

Los proyectos registran sus propios componentes con `GTEDITOR_COMPONENTS` en settings.

Catálogo inicial, priorizado por fase:

| Componente | Genera |
|---|---|
| `form` / campos | `GTForm` + `ModelForm`, `Meta.widgets` y `grid_representation` (`djgentelella/forms/forms.py`) |
| `object_management` | Serializers, FilterSet, `AuthAllPermBaseObjectManagement` o `BaseObjectManagement`, router, vista, plantilla con modales + `ObjectCRUD` |
| `inline_object_management` | `BaseInlineObjectManagement`, con un stub obligatorio de `get_parent_queryset()` |
| `crud_classic` | Subclase de `CRUDView` + `get_urls()` (`djgentelella/cruds/base.py`) |
| `chart` | `BaseChartGetter`/`VerticalBarChart`… en `gtcharts.py` con `@register_lookups`, más `gentelella/widgets/chartjs.html` en la plantilla |
| `stats` / `box_tile` | `djgentelella/elements.py` |
| `datatable` (solo lectura) | ViewSet + TableSerializer, al estilo de `demo/demoapp/datatables` |
| `map`, `calendar`, `timeline`, `cardlist` | Fases posteriores, siguiendo los ejemplos de `demo/demoapp/*` |
| `html` / `markdown` | Un bloque de plantilla libre |
| `notification_action` | Acción "al guardar / al transicionar": `send_email_from_template` o `create_notification` (ver §6c) |
| `flow_step` | Una vista o paso dentro de un flujo (ver §6d) |

### 5. Tabla de mapeo campo → widget/serializer (`gteditor/mapping.py`)

Hoy no existe en djgentelella; el demo elige los widgets a mano. Para cada tipo de
campo de modelo se define un widget por defecto y sus alternativas:

| Campo de modelo | Widget por defecto | Alternativas |
|---|---|---|
| CharField | `TextInput` | `TaggingInput`, inputs con máscara |
| TextField | `Textarea` | `EditorTinymce`, `TextareaWysiwyg`, `VoiceDictation` |
| IntegerField | `NumberInput` | `NumberKnobInput` |
| Float/DecimalField | `FloatInput` | — |
| DateField | `DateInput` | `DateMaskInput` |
| DateTimeField | `DateTimeInput` | — |
| BooleanField | `YesNoInput` | `CheckboxInput` |
| Campo con choices | `Select` | `RadioHorizontalSelect` |
| FK | `Select` | `AutocompleteSelect`, `TreeSelect` (si el destino es un TreeNode) |
| M2M | `SelectMultiple` | `AutocompleteSelectMultiple`, `FilteredSelectMultiple`, `CheckboxSelectMultiple` |
| FileField | `FileChunkedUpload` | `FileInput`, `PDFViewerWidget` |
| GTPointField | `MapPointInput` | — |

En el serializer: Date → `GTDateField`; FK y M2M → `GTS2SerializerBase`; File →
`GTBase64FileField`/`ChunkedFileField`.

**Dependencias implícitas.** Elegir `AutocompleteSelect` obliga a tener un lookup.
El generador reusa uno existente (encontrado por la introspección) o crea un
`BaseSelect2View` en `gtselects.py`. Lo mismo pasa con los upload views de
`PDFViewerWidget`.

### 6. Motor generador de código (`gteditor/codegen/`)

Es un pipeline puro de Python, usado igual desde la UI y desde
`manage.py gteditor_generate <design> [--dry-run|--write|--zip]`:

1. **Validar** el diseño contra el JSON Schema y contra la introspección: el modelo
   y los campos existen, y los permisos existen o se van a crear.
2. **Construir el IR.** Cada `ComponentSpec.contribute()` aporta "contribuciones"
   por archivo destino: imports, clases, entradas de url y router, plantillas,
   estáticos, menú y permisos. Las dependencias se resuelven y se deduplican.
3. **Renderizar con el motor de plantillas de Django.** djgentelella es Django
   templates de punta a punta, así que no se agrega Jinja2.
   - Se usa una instancia propia, `django.template.Engine(dirs=..., libraries=...)`,
     separada de la configuración `TEMPLATES` del proyecto. Así los context
     processors y loaders del proyecto no interfieren.
   - Una librería de tags `gtcodegen` aporta los helpers para emitir código:
     - `{% py_repr value %}` para literales Python seguros (`repr`, no
       interpolación cruda);
     - `{% py_imports ir %}`;
     - `{% djtag "block content" %}` / `{% djvar "form" %}` para emitir
       `{% ... %}` y `{{ ... }}` en las plantillas `.html` generadas, junto con
       `{% verbatim %}` para los trozos grandes.
   - DTL no tiene control fino de espacios. El formateo final de los `.py` lo
     hace ruff; para el HTML hay una normalización mínima (líneas en blanco
     múltiples, indentación de bloques).
   - Las plantillas se pueden sobrescribir desde el proyecto
     (`templates/gteditor/codegen/...`, como django-baker). El `Engine` busca
     primero en los dirs del proyecto.
   - Lo que se genera son **plantillas Django normales** que extienden
     `gentelella/base.html` y usan sus bloques (`pre_head`, `extra_css`,
     `content`, `js`) y sus tags (`define_true`, `define_urlname_action`,
     includes de `gentelella/blocks/*` y `gentelella/widgets/*`).
4. **Patrón *generation gap*** (la decisión clave para poder regenerar sin perder
   cambios). Todo lo generado vive en `<app>/gtgen/<slug>/`, que es **propiedad
   del generador** y se sobrescribe siempre:
   - `forms.py`, `serializers.py`, `api.py`, `views.py`, `charts.py`,
     `selects.py`, `urls.py`;
   - `templates/<app>/gtgen/<slug>.html`.

   Los archivos del usuario se tocan **una sola vez** para crear stubs con
   subclases (`class ProductForm(ProductFormBase): pass`), que el desarrollador
   personaliza y que no se vuelven a sobrescribir.
5. **Merge mínimo con `ast` (stdlib) + empalme de texto** en los archivos
   existentes de la app, siempre idempotente y con marcador `# gteditor: <slug>`.
   - `ast.parse` ubica los nodos: la asignación a `urlpatterns`, el último
     import, el método `ready()`, la clase `Meta`. Usa
     `lineno`/`end_lineno`/`col_offset`.
   - La inserción se hace como texto en esas líneas, así que se conserva el
     formato y los comentarios del usuario.
   - Antes de insertar se busca el marcador para no duplicar.
   - Después se vuelve a correr `ast.parse` para validar el resultado.
   - Si la estructura no es reconocible (por ejemplo, `urlpatterns` armado
     dinámicamente), no se toca el archivo: el ChangeSet muestra el fragmento
     para pegar a mano.

   Las inserciones son:
   - `urls.py`: `path('', include('<app>.gtgen.<slug>.urls'))`;
   - `gtcharts.py`/`gtselects.py`: `from .gtgen.<slug>.charts import *  # noqa`,
     porque `djgentelella/urls.py:import_module_app_gt` autodescubre solo esos
     nombres de módulo;
   - `models.py` (`Meta.permissions`), solo si se definieron permisos custom. En
     ese caso el editor avisa que hay que correr `makemigrations`.
6. **Menú y permisos.** Se genera una **data migration** idempotente (`RunPython`):
   - `MenuItem.objects.update_or_create(url_name=...)` con `permission` M2M;
   - si aplica, entradas de `PermissionsCategoryManagement`
     (`djgentelella/models.py:106`).

   Esto es reproducible en todos los ambientes, a diferencia de crear filas desde
   el editor.
7. **Permisos en las vistas**, según el componente:
   - vista de página: `all_permission_required`/`any_permission_required`
     (`djgentelella/decorators/perms.py`) o `PermissionRequiredMixin`;
   - object management: `AuthAllPermBaseObjectManagement` con un dict `perms`
     por acción;
   - classic: `CRUDView.perms`.

   Por defecto se usan los permisos de modelo `add_`/`change_`/`delete_`/`view_`.
8. **CSS/JS custom.** Se emiten `static/<app>/gtdesign/<slug>.{css,js}` y se
   incluyen en los bloques `extra_css` y `js` de `gentelella/base.html`. Los
   `use_*` necesarios (por ejemplo `use_maps`) se agregan como `{% define_true %}`
   en `pre_head`. A nivel de componente hay props `css_class` y `attrs`.
9. **Formateo y verificación.** Se corre `ruff format` + `ruff check --fix
   --select I` si ruff está instalado, y luego `compile()` de cada `.py`
   generado. Respeta el lint del proyecto: pycodestyle 88 y sin imports dentro de
   funciones.
10. **ChangeSet.** Para cada archivo: estado (nuevo, modificado o sin cambios),
    contenido viejo y nuevo, y diff unificado. Se puede aplicar todo o por
    archivo, con backup previo. Termina sugiriendo los comandos a correr:
    `makemigrations`, `migrate`, `createbasejs` si aplica.

La salida es determinista: el mismo diseño produce los mismos bytes. Esto se
prueba con golden files.

### 6b. Diseñador de menús

Es una pestaña *Menú* del editor que muestra el árbol de `MenuItem`
(`djgentelella/models.py`), leído de la BD local:
- categorías `main` (barra superior), `sidebar` y `sidebarfooter`;
- `parent`, `position`, `icon`/`only_icon` (con selector de íconos que usa las
  páginas `/icons/*` existentes);
- `url_name` + `is_reversed` + `reversed_kwargs`/`reversed_args`;
- `permission` (M2M), con un selector de los permisos del proyecto;
- `is_widget` para widgets de menú (`djgentelella/menu_widgets/`, como
  `PalleteWidget`).

Cómo se usa:
- Las páginas y flujos diseñados aparecen como entradas que se arrastran al árbol.
  Su `url_name` y sus permisos se proponen a partir del `meta` del diseño.
- La vista previa del menú usa `validate_menu_item`
  (`templatetags/gentelellamenu.py`) para simular la visibilidad. Se elige un
  usuario o grupo y se ve qué entradas ve.
- Cada app tiene un archivo de diseño de menú, `<app>/gtdesign/_menu.json`.
- **Salida:** una data migration en la app, con `RunPython` idempotente.
  `update_or_create` usa como clave natural `(category, parent title path,
  url_name)` e incluye una función reverse. La migración se regenera en un archivo
  nuevo solo si el menú cambió; no se edita una migración ya aplicada.
- No se escriben `MenuItem` directamente en la BD.

**Widgets de menú y footer** (`is_widget=True`). Hoy el `url_name` de un ítem
widget es el dotted path de una clase. Lo carga `get_menu_widget`
(`templatetags/_utils.py`), y las tags `top_menu`, `sidebar_menu` y
`footer_sidebar_menu` lo renderizan.

El protocolo que siguen esas clases, tomado de `PalleteWidget` en
`djgentelella/menu_widgets/palette.py`, es:
- `__init__(context)`;
- `render()`;
- `render_js()`;
- `render_external_html()` (lo inyecta `render_external_widget`);
- para el footer: `get_menu_item()` y, opcionalmente, `get_title`, `get_link` y
  `get_icon`.

El editor hace dos cosas con esto:
- **Reusar.** La introspección descubre las clases con ese protocolo: las de
  `djgentelella.menu_widgets.*` y las de las apps. Aparecen en la paleta del menú
  para colocarlas en `main`, `sidebar` o `sidebarfooter`.
- **Crear un widget nuevo.** Hay un componente `menu_widget` con ícono, título,
  contenido del panel (diseñado con el mismo canvas), JS y permisos. Se genera:
  - la clase en `<app>/gtgen/<slug>/menu_widgets.py`, con el stub de usuario
    `<app>/menu_widgets.py`;
  - sus plantillas Django en `templates/<app>/menu/`;
  - el `MenuItem(is_widget=True, url_name='<app>.menu_widgets.<Clase>')` en la
    data migration.

### 6b-bis. Ayuda contextual (widget Help)

djgentelella ya trae ayuda editable por vista:
- el modelo `Help(id_view, question_name, help_title, help_text)`;
- `PalleteWidget`, que aparece en el footer del sidebar como un ítem widget;
- `helper_widget.js` (`HelperBox`), el `HelpForm` y su serializer/API
  (`serializers/helper.py`, `widgets/helper.py`).

`id_view` es el `resolver_match.view_name` de la página.

En el editor, cada página, form y campo tiene una pestaña *Ayuda* en el panel de
propiedades, con un título y texto en TinyMCE.

Lo que se genera:
- una data migration con `Help.objects.get_or_create(id_view=<url_name del
  diseño>, question_name=<id del elemento>)`. No pisa la ayuda que después se
  edite en vivo desde el propio widget;
- si el diseño activa la ayuda y no existe el ítem `PalleteWidget` en
  `sidebarfooter`, se agrega al menú.

Hay que verificar en F4b qué `question_name` espera `HelperBox` para cada
elemento (selector o id del DOM). El código generado debe emitir esos mismos ids
en la plantilla.

### 6c. Integración con `async_notification` y notificaciones in-app

Hay dos tipos de acción que se pueden enganchar a "form guardado", "objeto
creado" o "transición de flujo":

**Email** con `djgentelella.async_notification.sending.send_email_from_template(code,
recipient, context)`. En el editor se define:
- el `code` del `EmailTemplate`: se reusa uno existente o se crea uno con asunto
  y cuerpo, con el preview en vivo del propio módulo;
- los destinatarios, usando los resolvers del módulo: un campo del objeto (por
  ejemplo `owner.email`), `group.local` o `<pk>@<app>.<model>.internal`;
- el contexto, que son los modelos del diseño.

El generador emite:
- `register_context(code, subject, models={...})` en `gtgen/<slug>/notifications.py`,
  dentro de una función `register()`. El merge con `ast` inserta una sola vez la llamada en el
  `AppConfig.ready()` de la app, con `# noqa: PLC0415`, porque es el patrón de
  `demo/demoapp/apps.py`;
- el `EmailTemplate` semilla como data migration (`get_or_create` por `code`, sin
  sobrescribir ediciones posteriores hechas en el admin);
- la llamada al envío en el hook correspondiente: `form_valid`/`perform_create`
  del viewset, o una acción del flujo.

**In-app** con `djgentelella.notification.create_notification(description, user,
message_type, link=..., send_email=...)`.

Todo esto es opcional y solo se habilita si `djgentelella.async_notification` está
en `INSTALLED_APPS`. La introspección lo detecta.

### 6d. Motor de flujos — en **djgentelella** (este repo, producción)

**Objetivo.** Encadenar varias vistas en un proceso con estados, transiciones,
permisos y acciones. Ejemplos: solicitud → revisión → aprobación/rechazo →
notificar; o un alta en pasos (wizard).

La responsabilidad se divide así:
- **`djgentelella/flows/`** es el runtime: pequeño, sin dependencias nuevas, y no
  hace introspección. Se usa también escrito a mano.
- **El editor** es solo un diseñador visual del flujo. Genera la clase `Flow`, los
  forms y las plantillas de cada paso.

Las opciones que se descartaron:
- **Viewflow:** AGPL con excepción y versión PRO comercial.
- **django-fsm-2 (MIT):** solo cubre la máquina de estados, y queríamos cero
  dependencias.
- **django-river:** sin mantenimiento.

**Runtime propuesto, a nivel de diseño.** El detalle de la API se fija en su
propio plan antes de F4.

- **Definición declarativa en Python:**
  ```python
  class SolicitudFlow(Flow):
      model = Solicitud
      states = [('draft', _('Borrador')), ('review', _('En revisión')),
                ('approved', _('Aprobada')), ('rejected', _('Rechazada'))]
      initial = 'draft'
      transitions = [
          Transition('submit', 'draft', 'review', form=SolicitudForm,
                     perms=['app.submit_solicitud'],
                     actions=[SendEmail('solicitud_enviada', to='group.revisores')]),
          Transition('approve', 'review', 'approved', perms=['app.review_solicitud'],
                     condition=lambda obj, user: obj.owner != user,
                     actions=[Notify(to='owner', message=_('Aprobada'))]),
          Transition('reject', 'review', 'rejected', form=MotivoForm, ...),
      ]
  register_flow(SolicitudFlow)   # autodescubierto en <app>/gtflows.py, como gtcharts
  ```
- **Estado.** Un modelo genérico `FlowInstance`: `content_type`, `object_id`,
  `flow`, `state`, `assigned_to`/`assigned_group`, timestamps. Va acompañado de
  `FlowTransitionLog` (quién, cuándo, de qué estado a cuál, datos del form). Todo
  vive en `djgentelella/models.py` y en `djgentelella/migrations/`, siguiendo la
  convención del repo: no es una app aparte. Así no se tocan los modelos del
  usuario y un modelo puede tener varios flujos.
- **Vistas genéricas:**
  - `FlowTransitionView` renderiza el GTForm de la transición, valida permisos y
    condición, aplica todo en `transaction.atomic`, corre las acciones y redirige;
  - `FlowInboxView` es la bandeja de "pendientes para mí": una tabla DataTables
    con las instancias por estado, asignación y permiso;
  - un widget/plantilla `flow_status` con el estado actual, los botones de las
    transiciones disponibles y el historial (timeline).
- **Acciones** en un registro extensible: `SendEmail` (async_notification),
  `Notify` (notification in-app), `SetField`, `Assign`, `CallFunction`
  (dotted path). Se ejecutan en la transacción o `on_commit` según el tipo.
- **Wizard.** Es un caso particular: una secuencia lineal de pasos con form, sobre
  un mismo objeto o borrador, con `FlowInstance` en estado intermedio.
- **Permisos:** por transición (`perms`), igual que `any/all_permission_required`.
  También se pueden agrupar en `PermissionsCategoryManagement`.
- **Auditoría:** `FlowTransitionLog` más el `LogEntry` que ya usa `history/`.

**Editor de flujos.** Es una pestaña *Flujo* con un diagrama de estados
(Cytoscape, el mismo motor del ERD):
- estados como nodos y transiciones como aristas;
- panel de propiedades de cada transición: form (enlazado al diseñador de forms),
  permisos, condición, asignación y acciones (email/notificación con el
  formulario de §6c).

El editor genera:
- `gtgen/<slug>/flow.py`;
- un stub del usuario en `<app>/gtflows.py`;
- forms y plantillas por transición;
- urls;
- entradas de menú (bandeja del flujo).

**Requisito de autodescubrimiento.** Hay que agregar `gtflows` a la lista de
módulos de `djgentelella/urls.py:import_module_app_gt`.

### 7. Interfaz del editor

**App independiente `/__gteditor__/`.** Usa `gentelella/base.html` (dogfooding),
pero con su propio bundle estático `static/gteditor/`, siguiendo el precedente de
`async_notification/static/`. Es a pantalla completa:

- **Barra superior:** lista de diseños (escanea `<app>/gtdesign/` de las apps
  permitidas), nuevo, guardar, validar, generar.
- **Izquierda:** explorador de apps → modelos → campos (se pueden arrastrar) y la
  paleta de componentes.
- **Centro, en pestañas:**
  - *Diagrama*: ERD con Cytoscape. Permite elegir qué modelos entran al diseño;
    hacer clic en una relación sugiere un inline o un autocomplete.
  - *Página*: canvas con SortableJS de filas, columnas y componentes. Soltar un
    modelo crea un `object_management` o un form; soltar un campo agrega el
    widget sugerido.
  - *Código*: árbol de archivos del ChangeSet con diff en CodeMirror merge.
  - *CSS/JS*: editores CodeMirror.
- **Derecha:** panel de propiedades del nodo seleccionado, generado desde
  `props_schema` (widget, label, ancho de columna, permisos, url, menú).
- **Preview vivo** en un `<iframe>` que apunta a `/__gteditor__/preview/<slug>/`.
  Renderiza con los widgets y el `javascript.html` reales de djgentelella, así que
  la página se ve igual que la final y el JS del editor no choca con el de los
  widgets. La selección se sincroniza con `postMessage`. El preview no escribe
  archivos: renderiza desde el IR en memoria.
- Deshacer/rehacer en el cliente y un borrador autoguardado en `localStorage`.

**Panel inyectado.** `gteditor.middleware.EditorPanelMiddleware`, con la misma
guarda, inserta antes de `</body>` un botón flotante. Al abrirlo muestra:
- url_name, vista y plantilla de la página actual;
- si la página fue generada, su diseño (detectado por el marcador
  `data-gteditor` en la plantilla).

Acciones del panel:
- "Abrir en editor" abre `/__gteditor__/?design=...` o `?from_url=...` en una
  pestaña nueva o un popup;
- "Nuevo diseño desde esta página".

El panel queda separado del editor completo porque un off-canvas es demasiado
chico para ERD + canvas + propiedades.

## Fases

| Fase | Entregable | Criterio de salida |
|---|---|---|
| **F0** Andamiaje | Repo `../djgentelella-editor` (GPL-2.0-or-later + `THIRD_PARTY_LICENSES.md` + chequeo de licencias en CI), pyproject, app `gteditor`, guardas + checks + URLs condicionales, testproject, CI (lint igual que djgentelella: pycodestyle 88 + ruff PLC0415) | Tests de las guardas: sin DEBUG falla el arranque; sin superusuario o fuera de `INTERNAL_IPS` da 403/404 |
| **F1** Introspección + ERD | API de esquema, pestaña Diagrama, `gteditor_graph` | Equivalente a django-model-visualizer sobre `demoapp` |
| **F2** Núcleo del codegen (sin UI) | JSON Schema v1, registro, mapping, IR, Engine de Django + tags `gtcodegen`, generation gap, merge con `ast`, ruff, ChangeSet; componentes `form` y `object_management`; `gteditor_generate` | Diseño golden → código que replica `demo/demoapp/object_management` y pasa `check`, `makemigrations --check`, lint, y un GET de la página que responde 200 |
| **F3** Editor de página | Canvas, propiedades, preview en iframe, diff y aplicar | Crear un CRUD de un modelo del demo de punta a punta desde la UI |
| **F4** Más componentes | `chart` (group_by/aggregate → `values().annotate()`), gtselects automáticos, `crud_classic`, inline, stats, CSS/JS custom | Página tipo dashboard con chart y tabla |
| **F4b** Menú, ayuda + notificaciones | Pestaña Menú → data migration (incluye widgets `is_widget` existentes y nuevos del footer); ayuda contextual → `Help` semilla; acciones de email/notificación (§6c) | El menú generado respeta los permisos; un widget de footer generado se renderiza; la ayuda aparece en `HelperBox`; un form que al guardar envía un email visible en MailHog |
| **F5a** Motor de flujos (repo djgentelella) | `djgentelella/flows/`, con su plan propio: `Flow`, `Transition`, acciones, `FlowInstance`/`FlowTransitionLog` + migración, vistas, bandeja, `gtflows` autodescubierto, docs y demo | Tests en `djgentelella.tests` (agregados a CI); ejemplo escrito a mano en `demoapp` |
| **F5b** Editor de flujos | Pestaña Flujo, generación de `flow.py` y de los forms/plantillas por transición | Un flujo de aprobación con 3 estados, generado de punta a punta, que pasa los tests de integración |
| **F6** Integración | Panel inyectado, "abrir en editor", importación inversa (GTForm/CRUDView existentes → diseño), plantillas del codegen sobrescribibles, Gridstack para dashboards | El panel funciona sobre páginas del demo |

## Cambios en djgentelella (este repo)

**Obligatorio (F5a): el motor de flujos `djgentelella/flows/`** (§6d):
- modelos en `djgentelella/models.py` + migración;
- vistas, plantillas y JS del widget de estado, con su entrada en `createbasejs`
  si lleva JS;
- `gtflows` en `import_module_app_gt`;
- docs en `docs/source/flows.rst`, ejemplo en `demoapp` y tests.

`makemigrations --check` y `check-dist` deben seguir pasando.

Opcionales:
- Mover la tabla campo → widget a `djgentelella/forms/` como `formfield_callback`
  reutilizable. Serviría también sin el editor.
- Mover `FIELD_TYPE_MAP` a un módulo común fuera de `async_notification`.
- Documentar en `docs/` cómo instalar el editor en dev (`INSTALLED_APPS` y URLs
  condicionales).

## Archivos de referencia (reuso)

- `djgentelella/forms/forms.py`: `GTForm`, `grid_representation`, render types.
- `djgentelella/forms/decorators.py`: `get_field_widget`, `decore_form_instance`.
- `djgentelella/objectmanagement.py`: `BaseObjectManagement`,
  `BaseInlineObjectManagement`, `AuthAllPermBaseObjectManagement`.
- `djgentelella/cruds/base.py`, `cruds/utils.py`: `CRUDView`, `crud_url_name`,
  `get_fields`.
- `djgentelella/chartjs.py`, `djgentelella/groute.py`: `BaseChartGetter`,
  `register_lookups`, `routes`.
- `djgentelella/urls.py`: `import_module_app_gt` (autodescubrimiento de `gt*.py`).
- `djgentelella/views/select2autocomplete.py`: `BaseSelect2View`.
- `djgentelella/models.py`: `MenuItem`, `PermissionsCategoryManagement`.
- `djgentelella/decorators/perms.py`, `djgentelella/templatetags/gtsettings.py`
  (`define_true`).
- `djgentelella/async_notification/introspection.py`: `FIELD_TYPE_MAP`,
  `describe_model_fields`.
- `djgentelella/async_notification/sending.py:send_email_from_template`,
  `async_notification/registry.py:register_context` (llamado en `AppConfig.ready`,
  como en `demo/demoapp/apps.py`), `async_notification/resolvers.py`.
- `djgentelella/notification/__init__.py:create_notification`.
- `djgentelella/templatetags/gentelellamenu.py:validate_menu_item`,
  `djgentelella/menu_widgets/`, `demo/demoapp/management/commands/demomenu.py`
  (forma de los `MenuItem`).
- `djgentelella/history/`: auditoría (`LogEntry`).
- `djgentelella/menu_widgets/palette.py:PalleteWidget` (protocolo de widget de
  menú/footer), `djgentelella/templatetags/_utils.py:get_menu_widget`,
  `render_external_widget`.
- `djgentelella/models.py:Help`, `djgentelella/static/gentelella/js/base/helper_widget.js`,
  `djgentelella/serializers/helper.py`, `djgentelella/forms/models.py:HelpForm`,
  `demo/demoapp/tests/selenium/test_help.py`.
- Patrón objetivo del código generado: `demo/demoapp/object_management/*`,
  `demo/demoapp/templates/object_management.html`, `demo/demoapp/gtcharts.py`,
  `demo/demoapp/gtselects.py`, `demo/demoapp/forms.py`.

## Verificación

- **Unitarias, en el repo del editor:**
  - guardas: DEBUG, callback, escritura fuera de `BASE_DIR` rechazada, symlinks;
  - introspección sobre `demoapp`;
  - validación del JSON Schema;
  - mapping;
  - idempotencia del merge con `ast`: aplicar dos veces no produce diff, y una
    estructura no reconocida cae en "fragmento manual" sin tocar el archivo;
  - licencias: `pip-licenses` + `THIRD_PARTY_LICENSES.md` contra la lista
    permitida.
- **Golden tests del codegen.** Diseños de ejemplo → árbol de archivos comparado
  byte a byte. El código generado:
  - compila;
  - pasa `ruff`/pycodestyle;
  - no importa `gteditor`.
- **Integración.** Copiar `demoapp` a un directorio temporal, aplicar el
  ChangeSet, y correr:
  - `manage.py check`;
  - `makemigrations --check` (salvo los permisos custom esperados);
  - `migrate`;
  - el test client con un GET de la página, el `list` de la API y un POST
    create/update.
- **Menú:** aplicar la data migration dos veces no duplica nada; con un usuario
  sin permiso, la entrada no aparece en `sidebar_menu`.
- **Notificaciones:** test de que el form guardado crea un `EmailNotification`
  con el `code` y los destinatarios esperados. En manual, verlo llegar en MailHog
  (`make mailhog`). Correr siempre `djgentelella.async_notification` a mano, ya
  que CI no lo corre.
- **Flujos (runtime):**
  - transición sin permiso → 403;
  - condición falsa → no se ofrece;
  - transición válida → cambia el estado, crea el log, corre las acciones en
    orden;
  - un fallo de una acción dentro de la transacción revierte todo;
  - la bandeja filtra por asignación.
- **Selenium (F3+),** con la infraestructura existente (`make test-selenium`):
  arrastrar un modelo, elegir el widget, generar y ver el diff.
- **Manual:**
  1. `pip install -e ../djgentelella-editor` en el venv del demo;
  2. agregar `gteditor` bajo `if DEBUG` y las URLs condicionales;
  3. abrir `/__gteditor__/` y crear un CRUD de `ObjectManagerDemoModel`;
  4. aplicar y navegar a la página generada.
