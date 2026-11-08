# codi-informal

Bot de WhatsApp que cobra con CoDi. Hackatón OpenAI DevDay Exchange, Ciudad de México, 7 y 8 de noviembre de 2026.

No hay frontend. El dueño escribe o manda una nota de voz, el bot pide el push o el QR a pey, y cuando el pago entra se lo avisa en el mismo chat.

La idea y el corte están en [IDEA.md](IDEA.md). Los campos de la API que sí usamos están en [docs/pey-api.md](docs/pey-api.md).

Los requisitos de seguridad antes de habilitar cobros están en [docs/guardrails.md](docs/guardrails.md).

## Estado

Esqueleto del bot. Falta la API key de pey y el token de WhatsApp para cobrar de verdad.

## Cómo se le habla

- `cobra 0.01 al 5512345678`
- `manda el qr del puesto`
- `qué se ha cobrado`

Una nota de voz o la foto del ticket caen en las mismas frases: se leen con OpenRouter (`OPENROUTER_API_KEY`); sin llave o si no se entiende, el bot pide el texto.

## Cómo correr

```bash
cp .env.example .env
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
