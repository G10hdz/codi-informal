# Plan en paralelo: 3 agentes

Depende de `roadmap.md` y `docs/guardrails.md`. Corte: domingo 8 de noviembre de 2026, 1:00 p.m.

## Reglas

- Un agente, un worktree, una rama: `~/agent-configs/scripts/wt.sh new <nombre> feature/<nombre>`.
- La unidad de exclusividad es el archivo. Cada archivo tiene un solo dueño por ola. Si hace falta tocar uno ajeno, se pide al dueño o se espera a la ola 2.
- Los commits (`add`, `commit`, `rebase`) se serializan entre sesiones. Si aparece `index.lock`, no se borra: se confirma que la otra sesión está quieta.
- Cada PR es un cambio lógico, menos de 400 líneas. Test primero: rojo, luego verde.
- Review de otra persona antes de mergear. Rebase and merge a `main`.
- Sin CLABEs, tickets reales ni `.env` en git.

## Dueños de archivos

| Agente | Rama | Archivos propios |
|---|---|---|
| A. Entrada | `feature/entrada` | `server.py`, `whatsapp.py`, `limites.py` (nuevo), `tests/test_entrada.py` |
| B. Cobro | `feature/cobro` | `agente.py`, `pey.py`, `registro.py`, `confirmacion.py` (nuevo), `tests/test_cobro.py` |
| C. Multimodal | `feature/multimodal` | `voz.py`, `idioma.py`, `ticket.py` (nuevos), `tests/test_multimodal.py` |

`firma.py` no se toca. Las specs y `docs/` se editan en el PR que cambia el comportamiento que describen.

## Ola 1: en paralelo (hoy)

### A. Entrada (G01, G05, G07, parte de G08)

1. Validar `X-Hub-Signature-256` en `POST /webhooks/whatsapp`. Sin app secret o firma mala: 401, sin tocar agente ni pey.
2. Lista cerrada de dueños (`OWNER_WHATSAPP`). Remitente desconocido o grupo: se ignora antes de transcribir o llamar al agente.
3. Deduplicar por `message id` de WhatsApp, persistente. La repetición recibe 200 sin efecto.
4. Tope de `Content-Length` (por ejemplo 64 KB) y 2,000 caracteres de texto.
5. Límites por dueño (`limites.py`): 10 mensajes por minuto, 3 cobros por minuto. Sin almacenamiento, se bloquea el cobro.
6. Mandar la imagen del QR por WhatsApp con `multipart_imagen`, o dejar el QR como texto si no alcanza.
7. `_avisar` deja registro de fallo, sin cuerpos ni teléfonos completos.

Listo cuando: webhook falsificado, remitente ajeno y mensaje repetido no llegan a pey; test por cada punto.

### B. Cobro (G03, G04, G05, G06, REQ-1 a 6)

1. Dinero en centavos enteros. 0.005, 0.001, negativos, no finitos: rechazo, no redondeo. `PEY_MAX_AMOUNT` mayor que 0.01 o inválido: cobros deshabilitados.
2. Confirmación de un solo uso (`confirmacion.py`): ligada a dueño, chat y datos exactos del borrador, vence en 2 minutos. Cambiar un dato la invalida.
3. Tabla de operaciones: se guarda la operación antes de llamar a pey. Timeout queda como `incierto`, sin reintento.
4. Conciliar el webhook con la operación creada: monto y cuenta coinciden, si no queda pendiente.
5. Cubrir los huecos de test: 401 sin secreto, QR en cero, `/mensaje` sin key (REQ-6).
6. Exponer un solo punto de entrada para B-2: `Agente.cobrar(telefono, monto, concepto)`, que C y los demás reusan.

Listo cuando: los 6 REQ de `01-whatsapp-codi.md` tienen test propio y los casos de monto, confirmación y timeout de la tabla P0 pasan.

### C. Multimodal (REQ-8 a 15), solo módulos puros

No toca `agente.py` ni `server.py` en esta ola. Entrega funciones con interfaz fija:

1. `voz.transcribir(audio_id) -> str | None`: descarga acotada (60 s, 5 MB) y transcripción con el proveedor configurado. Sin proveedor, devuelve `None`.
2. `idioma.detectar(texto) -> "es" | "en" | None` y `idioma.mensaje(clave, idioma)`. Ambiguo cae en `es`.
3. `ticket.leer(imagen) -> {"monto", "concepto"} | None`. No guarda la imagen ni números de cuenta.
4. Fixtures sintéticos, sin tickets de personas.

Listo cuando: cada función tiene test con doble de proveedor y los tests de REQ-8, 9, 11, 12, 13 y 15 a nivel módulo pasan.

## Ola 2: integración (serializada)

Entra cuando A y B estén en `main`.

1. Orden de merge: B, luego A, luego C. B define `Agente.cobrar`; A cambia `server.py`; C cuelga de ambos.
2. Un solo agente (C) integra: `atender` usa `voz.transcribir`, el agente contesta con `idioma.mensaje`, la foto pasa por `ticket.leer` y confirma con el flujo de B (REQ-14).
3. Tests de integración de REQ-8 a 15 con el servidor completo.

## Ola 3: despliegue y prueba (antes de las 1:00 p.m.)

1. Alguien del equipo es operador y tiene el interruptor de paro (G09): `COBROS_ACTIVOS=0` detiene cobros nuevos y sigue conciliando.
2. Deploy con llave de pey, secreto de webhook, número de WhatsApp y app secret.
3. Prueba real de $0.01 con participantes informados. Se anota el commit probado en el PR.
4. Altagracia completa los cinco pasos de `REQUERIMIENTOS.md`.

## Si falta tiempo, se recorta en este orden

1. Imagen del QR por WhatsApp (queda texto).
2. Idiomas y foto del ticket (C se queda en voz).
3. Límites de ráfaga (G07), sin soltar firma, lista de dueños, tope de monto y deduplicación.

No se recorta: G01, G03, G04, G05, G06.

## Después del corte

NFC (`03-nfc.md`) y comunidad (`04-comunidad.md`) no entran antes del domingo (NG-11). Se retoman con el mismo reparto por archivos.
