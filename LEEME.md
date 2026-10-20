# UDA · Unión de Arquitectos – Publicación automática

Publica sola, cada día, **3 reels con voz y un carrusel** en **Instagram, TikTok y LinkedIn** (@uniondearquitectos, todo vía
**Zernio**) para que los arquitectos de **toda España** sigan la cuenta y, cuando vayan justos de equipo, deleguen sus
Proyectos Básicos y de Ejecución en **uniondearquitectos.com**. Es el mismo motor que *Aprueba TCAE* (verificador, piloto
automático, agentes, voz controlada por reconocimiento de voz), adaptado a UDA.

| Hora (España) | Qué | Instagram | TikTok | LinkedIn |
|---|---|---|---|---|
| 8:00 | Reel (`manana`) | Story (el reel completo) | Reel | — |
| 14:30 | Reel (`mediodia`, serie del día) | Reel + story de 12 s | Reel (+ story al buzón como borrador) | — |
| 18:00 | Carrusel | Carrusel | Carrusel de fotos | **Documento PDF** (1 al día) |
| 21:30 | Reel (`noche`) | Reel + story de 12 s | Reel (+ borrador) | — |

**LinkedIn: como máximo una publicación al día.** Por defecto es el carrusel (como documento PDF, el formato de carrusel
de LinkedIn). Con la variable `LINKEDIN` = `manana`, `mediodia` o `noche` va ese reel en su lugar; `false` lo apaga. El
código comprueba antes de publicar que hoy no hay ya nada en LinkedIn. Sin YouTube.

## Contenido: 4 bloques
| Bloque | Qué | De dónde sale |
|---|---|---|
| **Normativa** | CTE y sus DB, LOE, certificación energética, seguridad y salud, residuos, Ley de Suelo, Propiedad Horizontal | Texto oficial del **BOE** |
| **Proyecto** | Consejos de proyecto: qué comprobar, incluir o justificar | Texto oficial del **BOE** |
| **Productividad** | Escalar la facturación del despacho, contratar frente a delegar | Documentos y web de UDA |
| **Servicios** | Qué hace UDA, partidas, precios de referencia, pagos 60/40, CAD o Revit | Documentos y web de UDA |

Los servicios salen **solo** de la *Tabla de Referencia de Presupuestos 2026*, del *Listado de Documentos a Delegar*
(transcritos en `fuentes/uda_*.txt`) y de la web. Los precios se presentan siempre como precios de referencia y nunca se
dice que UDA firma: la firma es del despacho.

## Formatos de reel
| Formato | Qué es |
|---|---|
| `test_normativa` | Pregunta tipo test, cuenta atrás, solución en bronce y explicación con su fuente |
| `error_tipico` | Marca la opción trampa y explica por qué engaña |
| `mito_realidad` | Afirmación, cuenta atrás y sello MITO / REALIDAD |
| `norma_30s` | 3 ideas clave de una norma + pregunta rápida |
| `simulacro_3` | 3 preguntas cortas seguidas; "¿cuántas has acertado?" |
| `caso_despacho` | Escena de despacho ("Te entra un encargo de 12 adosados…") que lleva a la pregunta |
| `checklist` | 3 claves de proyecto (sin pregunta) |
| `delegar` | 3 claves de productividad: contratar o delegar |
| `uda_servicio` | 3 claves de cómo trabaja UDA |
| `repaso_express` | 4 fichas que se giran; "¿cuántas sabías?" |

**Series fijas (14:30):** lunes normativa · martes errores de proyecto · miércoles despacho (delegar) · jueves checklist ·
viernes mitos · sábado repaso · domingo test. Las 8:00 y las 21:30 las elige el piloto automático, que aprende de los
resultados reales (guardados, compartidos, comentarios, clics, visionado) y además deja descansar los formatos comerciales
(`uda_servicio` como mucho 1 de cada 6 reels, `delegar` 1 de cada 3) para que la cuenta no parezca un anuncio.

**Carrusel (18:00):** lunes normativa · martes proyecto · miércoles productividad · jueves normativa · viernes servicios ·
sábado normativa · domingo proyecto. Portada carbón, 3-5 diapositivas con fuente, "¿Te atreves?" con un test verificado y
cierre con UDA.

**Estilos visuales** (los prueba el piloto): `piedra` (como los documentos), `carbon`, `plano` (ejes y cotas), `ficha`
(cajetín de plano), `minimal`, `ilustrado` (imagen de arquitectura generada y revisada por IA). Colores de los documentos
(carbón `#2b2b2b`, piedra `#f3f0ec`/`#d8d2ca`, bronce `#7a6a58`, arena `#c9b9a6`) y su misma tipografía: **TeX Gyre
Adventor** (geométrica, licencia libre GUST, en `fonts/`). Sin pegatinas ni confeti.

**Voz:** masculina, de colega a colega, con energía (Gemini, voz `Orus` por defecto; elige otra con *Muestras de voz*).
Cada toma se transcribe: si dice algo que no está en el guion, repite o lee una indicación, se graba otra. Las siglas se
leen como las dice un arquitecto ("de be ese i", "ce te e", "la loe", "metros cuadrados", "unión de arquitectos punto com").

## Cómo se evita publicar un error (lo más importante)
1. **Banco de piezas** (`generar_banco.py`): cada pieza (test, 3 claves o ficha) se escribe a partir de UN fragmento real
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
| `LINKEDIN` | `carrusel` | Qué va a LinkedIn (`carrusel`, `manana`, `mediodia`, `noche`, `false`) |
| `IG_STORY`, `TIKTOK`, `TIKTOK_STORY_BORRADOR` | `true` | Interruptores (o el nombre de un hueco) |
| `CARRUSEL` | `true` | `false` apaga el carrusel |
| `LINKEDIN_ORG_URN` | — | Fuerza una página de empresa concreta (`urn:li:organization:…`) |
| `ZERNIO_MATCH` | `uniondearquitectos` | Nombre que deben tener las cuentas en Zernio |
| `PUBLISH_MAX_WAIT_MIN` | `0` | Esperar a la hora exacta (gasta minutos) |
| `ELEVENLABS_VOICE_ID` (+ secreto `ELEVENLABS_API_KEY`) | — | Voz de ElevenLabs (opcional, de pago) |

## Workflows
| Workflow | Cuándo | Qué |
|---|---|---|
| Reels diarios | 7:30, 13:57, 20:57 | Genera, verifica y publica el reel |
| Carrusel diario | 18:00 | Carrusel en Instagram, TikTok y LinkedIn |
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
