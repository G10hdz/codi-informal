# Varísimo

[Landing](https://varisimo.vercel.app) · [Video](https://youtu.be/Z2V4W_uf4ns) · [Release v0.1.0](https://github.com/G10hdz/codi-informal/releases/tag/v0.1.0)

Varísimo es un bot de WhatsApp que cobra con CoDi para quien vende en la informalidad. Es el proyecto del equipo para el Hackatón OpenAI DevDay Exchange, Ciudad de México, 7 y 8 de noviembre de 2026. El repo se llama `codi-informal`.

No hay frontend. El dueño escribe o manda una nota de voz, el bot pide el push o el QR a pey, y cuando el pago entra se lo avisa en el mismo chat.

La idea y el corte están en [IDEA.md](IDEA.md). Los campos de la API que sí usamos están en [docs/pey-api.md](docs/pey-api.md). La página del proyecto, con un chat de prueba, está en https://varisimo.vercel.app ([site/index.html](site/index.html)).

Los requisitos de seguridad antes de habilitar cobros están en [docs/guardrails.md](docs/guardrails.md).

Diagramas de la arquitectura, de un cobro y de los estados de una operación, más un explicador interactivo: [docs/diagramas](docs/diagramas/README.md).

## Cómo se ve

![Arquitectura](docs/diagramas/arquitectura.svg)

También hay un diagrama de [secuencia de un cobro](docs/diagramas/secuencia.svg), otro de los [estados de una operación](docs/diagramas/estados.svg) y un [explicador interactivo](docs/diagramas/como-funciona.html) con recorrido paso a paso, hecho con legibify, el skill de Gio.

## Estado

Desplegado en un VPS; cómo está montado y cómo se sube una versión nueva está en [docs/deploy.md](docs/deploy.md). La decisión de la puerta por WhatsApp está en [docs/adr/0001-puerta-whatsapp.md](docs/adr/0001-puerta-whatsapp.md). Notas de la entrega del hackatón: [docs/entrega.md](docs/entrega.md).

- WhatsApp por Kapso o por la Cloud API de Meta, según `WHATSAPP_PROVIDER`.
- Cobros con CoDi a través de pey. El tope de prueba es `PEY_MAX_AMOUNT` (0.01 por omisión).
- OpenRouter para leer notas de voz y fotos de tickets.

## Cómo se le habla

- `cobra 0.01 al 5512345678`
- `manda el qr del puesto`
- `qué se ha cobrado`

Una nota de voz o la foto del ticket caen en las mismas frases: se leen con OpenRouter (`OPENROUTER_API_KEY`); sin llave o si no se entiende, el bot pide el texto.

## Proveedor de WhatsApp

Por omisión habla con la Cloud API de Meta (`WHATSAPP_PROVIDER=meta`). Con `WHATSAPP_PROVIDER=kapso` el mismo tráfico sale y entra por el proxy de Kapso: `api.kapso.ai/meta/whatsapp/v24.0`, autenticado con `KAPSO_API_KEY` en la cabecera `X-API-Key`. El webhook se registra en Kapso con el evento `whatsapp.message.received` y se verifica con `KAPSO_WEBHOOK_SECRET` (firma HMAC en `X-Webhook-Signature`). Con Kapso el `phone_number_id` viene en el nivel superior del evento, no en `metadata` como en Meta, y el `hub.challenge` solo lo usa Meta.

## Cómo correr

Python 3.12 o más nuevo, sin dependencias externas.

```bash
cp .env.example .env
set -a; . ./.env; set +a   # el bot lee variables de entorno; no abre el archivo .env
PYTHONPATH=. python3 -m unittest discover -s tests
PYTHONPATH=. python3 -m codi_informal
```

El proceso escucha en `127.0.0.1:8787`. Para probar sin WhatsApp:

```bash
curl -s localhost:8787/mensaje \
  -H 'content-type: application/json' \
  -d '{"texto":"cobra 0.01 al 5512345678"}'
```

Si pey no contesta a tiempo, el cobro queda incierto y ese dueño no puede pedir otro. El operador lo revisa en pey y lo cierra:

```bash
PYTHONPATH=. python3 -m codi_informal.registro                          # lista los inciertos
PYTHONPATH=. python3 -m codi_informal.registro resolver <op_id> fallida  # o creada, si sí salió
```

`COBROS_ACTIVOS=0` pausa los cobros nuevos; los pagos en camino se siguen conciliando.

## Equipo

- Gio: https://github.com/G10hdz
- Jeaneth: https://github.com/jeanethS
- Syn: https://github.com/syndeldebby
- Altagracia: miembro del equipo. Aporta ideas desde su experiencia y prueba los flujos. No escribe código.

## Documentación de pey

- Lo que usa este repo: [docs/pey-api.md](docs/pey-api.md)
- Referencia: https://docs.pey.mx
- Portal del correo del hackatón: https://portal.pey.mx
- Portal de la doc de pey, donde se configura el webhook: https://portal.mipey.mx/developers
