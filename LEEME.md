# UDA · Unión de Arquitectos – Publicación automática

Publica sola, cada día, **3 reels con voz y 1 carrusel** en **Instagram** (directo por la API de Meta), **TikTok** y
**LinkedIn** (vía Zernio) como @uniondearquitectos. Público: **fundadores y socios de despachos de arquitectura y
arquitectos autónomos** que proyectan bloques, promociones y edificios de envergadura. Objetivo: que vean, con datos
ciertos y criterio de socio senior, que delegar la documentación técnica en UDA les hace facturar más y cobrar mejor su
hora. Contenido premium y elegante: ni repaso de examen ni teletienda.

| Hora (España) | Qué | Instagram | TikTok | LinkedIn |
|---|---|---|---|---|
| 8:00 | Reel (`manana`) | Reel + story de 12 s | Reel (+ story al buzón) | — |
| 12:00 | Reel (`mediodia`, serie del día) | Reel + story | Reel (+ story al buzón) | — |
| 15:00 | Reel (`tarde`) | Reel + story | Reel (+ story al buzón) | — |
| 18:00 | Carrusel | Carrusel | Carrusel de fotos | **Documento PDF** (1 al día) |

Cada workflow arranca ~45 min antes, genera, verifica y revisa, y **espera a la hora exacta** para publicar.
**LinkedIn: como máximo una publicación al día** (por defecto el carrusel; con `LINKEDIN` = `manana`, `mediodia` o
`tarde` va ese reel). El cambio de horario verano/invierno se gestiona solo.

## Contenido: 4 bloques
| Bloque | Qué | De dónde salen los datos |
|---|---|---|
| **Negocio** | Facturar más delegando, mejorar el precio/hora, productividad, crecer sin ampliar plantilla | Documentos y web de UDA |
| **Contratar** | Contratar a alguien indefinidamente frente a contratar por servicios | Estatuto de los Trabajadores (BOE) + documentos de UDA |
| **Servicios** | Todo lo que UDA hace y lo que implicaría hacerlo con equipo propio | Tabla de presupuestos, listado de documentos y web |
| **Proyecto** | Datos de Proyectos Básicos y de Ejecución que pocos conocen | CTE y sus DB, LOE, RD 390/2021, RD 1627/1997, RD 105/2008 (BOE) |

Se admiten conclusiones y consejos razonados, pero **toda cifra sale literal de una fuente**; los precios van siempre
como precios de referencia y nunca se dice que UDA firma (la firma es del despacho).

## Formatos de reel
| Formato | Qué es |
|---|---|
| `claves` | 3 claves (facturar más, precio/hora, qué implica una tarea...) que aparecen al decirlas |
| `comparativa` | Dos columnas enfrentadas ("Contratar en plantilla" / "Contratar por servicios", "En tu despacho" / "Delegado en UDA") |
| `dato` | Un dato de proyecto que pocos conocen + por qué le importa al despacho |
| `mito_realidad` | Una creencia habitual del despacho, cuenta atrás y sello MITO / REALIDAD |
| `caso_despacho` | Escena ("Te entra un encargo de 80 viviendas y tu equipo ya va a tope…") + 3 claves |

**Series (12:00):** lunes facturación (claves) · martes contratar o delegar (comparativa) · miércoles datos de proyecto ·
jueves mitos del despacho · viernes casos de despacho · sábado lo que delegas (comparativa) · domingo productividad.
Las 8:00 y las 15:00 las elige el piloto automático, que aprende de los resultados reales.

**Carrusel (18:00):** lunes negocio · martes datos de proyecto · miércoles contratar o delegar · jueves servicios ·
viernes negocio · sábado datos de proyecto · domingo servicios.

**Calidad mínima:** cada pieza tiene una nota de calidad del verificador (≥ 7 para entrar); cada reel necesita **8 o
más** de la directora de arte y del revisor del vídeo, y cada carrusel 8 o más de su revisión. Si no llega, se prueba
otro formato o tema; si nada llega, ese hueco no se publica.

**Estilo visual**: `negro` (identidad premium: fondo negro, tarjetas grafito con filete de oro `#c8a45d`, texto crema `#f2ece0`, fotos de arquitectura en clave baja con luz dorada). Es el único que usa el piloto; los antiguos (`piedra`, `carbon`, `plano`, `ficha`, `minimal`, `ilustrado`) siguen disponibles a mano. El carrusel usa la misma paleta. Tipografía: **TeX Gyre Adventor**.

**Voz:** masculina, de socio senior, con energía (Gemini, `Orus` por defecto; elige otra con *Muestras de voz*).

## Cómo se evita publicar un error (lo más importante)
1. **Banco de piezas** (`generar_banco.py`): cada pieza (3 claves, comparativa, dato o mito) se escribe a partir de UN fragmento real
   de su fuente y trae su **cita literal**; el código comprueba que la cita está de verdad en el texto, que toda cifra
   está en la fuente, que un precio va como precio de referencia y que nunca dice que UDA firma. Lo que no pasa, se tira.
2. **Verificador** (`verifier.py`, otro modelo más estricto): revisa cada pieza contra el texto del BOE o de UDA. Solo las
   "ok" con cita comprobada se publican. Si dos fuentes de UDA no coinciden, la pieza queda "dudosa".
3. **Verificación del guion**: todo lo que escriben los agentes (ganchos, explicación, trampa, mito, cierre, descripción)
   se contrasta con la pieza, su fuente y `assets/uda/hechos.md`. Si no pasa, se reescribe; si no, se cambia de formato.
4. Si no hay nada verificado, **ese día no se publica**.

`banco/informe_verificacion.md` lista las piezas dudosas o con error (nunca se publican).

## Puesta en marcha (una vez)
1. **Settings → Secrets and variables → Actions → Secrets**:
   - `GEMINI_API_KEY` (obligatorio: generador, verificador, guion, voz).
   - `IG_TOKEN`: Instagram va **directo por la API de Meta** (gratis, como en TCAE): token de **página** de Facebook
     (empieza por `EAA`) de la página vinculada a @uniondearquitectos, con `instagram_basic`, `instagram_content_publish`,
     `pages_show_list`, `pages_read_engagement` e `instagram_manage_insights`, generado desde un token de usuario de larga
     duración (no caduca). El código comprueba que es de @uniondearquitectos antes de publicar.
   - `ZERNIO_API_KEY`: en Zernio conecta **TikTok y LinkedIn de @uniondearquitectos** (en LinkedIn, la página de
     empresa); son las 2 cuentas del plan gratuito. Zernio también aloja las imágenes del carrusel. Por seguridad solo se publica en cuentas cuyo nombre contiene "uniondearquitectos" (o "Unión de
     Arquitectos"): aunque el mismo Zernio tenga conectada @apruebatcae, nunca se publica allí. Si alguna se llama de otra
     forma, pon su id en las variables `ZERNIO_IG_ACCOUNT`, `ZERNIO_TT_ACCOUNT` o `ZERNIO_LI_ACCOUNT`.
2. **Actions → Descargar fuentes → Run workflow.** Mira `fuentes/estado.md` (ver la nota sobre el CTE más abajo).
3. **Actions → Generar banco → Run workflow** con `llamadas` = 40 (la primera vez). Crea y verifica las primeras ~100
   piezas. Después se repite solo cada domingo.
4. **Actions → Muestras de voz**: escucha las voces masculinas y pon la elegida en **Variables → `GEMINI_VOICE`**.
5. **Actions → Reels diarios → Run workflow** con "Solo generar el vídeo" marcado (prueba algún formato). Descarga el
   vídeo en *Artifacts*. Igual con **Carrusel diario**.
6. **Actions → Comprobar conexiones**: todo en verde.
7. **Variables → `ACTIVO` = `true`.** Hasta entonces nada programado se ejecuta (las pruebas a mano sí).

## Nota sobre el CTE en el BOE
El texto consolidado del Real Decreto 314/2006 en el BOE trae la **Parte I** (artículos, exigencias básicas, Anejo I
"contenido del proyecto", Anejo III terminología), pero los **Documentos Básicos** no vienen como texto. Por eso el
descargador intenta además los reales decretos que publicaron los DB en el BOE (RD 732/2019: DB HE y cambios en HS y SI;
RD 450/2022; RD 173/2010: DB SUA; RD 1371/2007: DB HR) y comprueba que el título descargado sea el correcto. En
`fuentes/estado.md` verás cuáles han entrado. Si alguno falta, sus temas simplemente no se usan (hay de sobra con el
resto). Los textos antiguos llevan una nota de vigencia: el verificador marca "dudosa" cualquier apartado que pueda
haber cambiado.

## Variables (Settings → Variables)
| Variable | Por defecto | Qué hace |
|---|---|---|
| `ACTIVO` | (vacía) | `true` enciende todo lo programado |
| `GEMINI_VOICE` | `Orus` | Voz de Gemini |
| `LINKEDIN` | `carrusel` | Qué va a LinkedIn (`carrusel`, `manana`, `mediodia`, `tarde`, `false`) |
| `IG_STORY`, `TIKTOK`, `TIKTOK_STORY_BORRADOR` | `true` | Interruptores (o el nombre de un hueco) |
| `CARRUSEL` | `true` | `false` apaga el carrusel |
| `LINKEDIN_ORG_URN` | — | Fuerza una página de empresa concreta (`urn:li:organization:…`) |
| `ZERNIO_MATCH` | `uniondearquitectos` | Nombre que deben tener las cuentas en Zernio |
| `PUBLISH_MAX_WAIT_MIN` | `50` | Minutos máximos de espera para publicar a la hora exacta |
| `ELEVENLABS_VOICE_ID` (+ secreto `ELEVENLABS_API_KEY`) | — | Voz de ElevenLabs (opcional, de pago) |

## Workflows
| Workflow | Cuándo | Qué |
|---|---|---|
| Reels diarios | 7:15, 11:15, 14:15 (publica a las 8:00, 12:00, 15:00) | Genera, verifica y publica el reel |
| Carrusel diario | 17:25 (publica a las 18:00) | Carrusel en Instagram, TikTok y LinkedIn |
| Generar banco | Domingos | Piezas nuevas + verificación |
| Verificar banco | Lunes y jueves | Verifica lo pendiente |
| Descargar fuentes | Día 1 de cada mes | Refresca BOE y web |
| Comprobar conexiones | Lunes | Zernio, Gemini, reserva del banco, fuentes y publicaciones |
| Muestras de voz | A mano | Voces masculinas para elegir |

El repositorio es público: los minutos de GitHub Actions no tienen límite. Los secretos no se ven nunca.

## Lo demás
- **Hechos de UDA**: `assets/uda/hechos.md`. Los agentes solo afirman sobre UDA lo que pone ahí (edítalo si algo cambia).
- **Si cambia la tabla de precios**: sustituye `fuentes/uda_tabla_presupuestos.txt` (y `hechos.md`). Las piezas antiguas
  con precios viejos: bórralas de `banco/piezas.json` o márcalas como "error" en `banco/verificacion.json`.
- **Aprendizaje**: `performance.json` (métricas de Zernio por publicación y por red), `strategy_report.md`, `playbook.md` y
  `agents/*.md` (cuadernos de los 15 agentes, reescritos cada día).
- **Guardado sin choques**: todos los workflows guardan su estado con `sincronizar.py`, que fusiona antes de subir.
- **Prueba local sin red**: `QUIZ_MOCK=1 VOICE_ENGINE=mock python make_quiz.py checklist out/prueba.mp4 plano`
  (necesita piezas en el banco).
