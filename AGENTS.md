# Agentes en este repo

La spec manda. El código que no esté en `specs/` no se inventa.

## Trabajo en paralelo

Una sesión, un worktree. No se cambia de rama en la carpeta de otra persona.

```bash
~/agent-configs/scripts/wt.sh new <nombre> feature/<nombre>
```

Cada cambio entra por PR a `main`. Se empuja la rama al terminar el commit. `main` se queda para pull.

## Qué se construye

No hay frontend en el corte del hackatón. La puerta es WhatsApp: texto, nota de voz, foto de ticket y, cuando exista el tap, NFC. El frontend posterior (página del puesto, libreta y landing) está definido en `specs/06-front.md`. El cobro de verdad es CoDi por pey: push o QR. Los campos válidos están en `docs/pey-api.md`. Si un endpoint no está ahí, no se llama.

El tope de prueba es `PEY_MAX_AMOUNT` (0.01 si nadie lo cambia). Los pagos no se devuelven.

Altagracia prueba los flujos. No se le pide que escriba código.

## Avances en imagen

Cada avance visible se dibuja con Vertex Imagen y se guarda en `avances/`. Esa carpeta está en `.gitignore`. No se hace commit de las imágenes ni se pegan CLABEs, teléfonos reales ni tickets de personas.

## Comandos

```bash
PYTHONPATH=. python3 -m unittest discover -s tests
PYTHONPATH=. python3 -m codi_informal
```

## No va en git

`.env`, CLABEs, secretos de webhook, `avances/`, `data/`.
