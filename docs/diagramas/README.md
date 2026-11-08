# Diagramas

Cómo está armado Varísimo y cómo viaja un cobro. Cada nodo y cada flecha apuntan a un archivo y una línea de `codi_informal/`. Si el código cambia y el diagrama no, el diagrama miente: se rehace en el mismo PR.

| Qué muestra | Página | Imagen |
|---|---|---|
| Arquitectura: WhatsApp, Caddy, servidor, agente, registro, pey y OpenRouter | [arquitectura.html](arquitectura.html) | [arquitectura.svg](arquitectura.svg) |
| Secuencia de un cobro, de la orden al aviso "Entró un pago" | [secuencia.html](secuencia.html) | [secuencia.svg](secuencia.svg) |
| Estados de una operación: creando, creada, incierto, fallida, pendiente y pagado | [estados.html](estados.html) | [estados.svg](estados.svg) |
| Explicador interactivo con recorrido paso a paso y preguntas | [como-funciona.html](como-funciona.html) | |

Las páginas `.html` se abren en el navegador, con tema claro y oscuro. Los `.svg` se adaptan solos al tema del sistema. En el celular, el diagrama se desliza de lado.

Explicador hecho con [legibify](https://github.com/G10hdz/legibify), el skill de Gio.

## Notas

- El estado `pendiente` existe en el código (`registro.py:147` y `:273`) aunque no sea de los cinco que se suelen nombrar. Está en el diagrama de estados.
- El código no usa Doppler. Las llaves se leen del entorno y viven en `/opt/codi-informal/.env` en el VPS ([deploy.md](../deploy.md)).
- El paso del banco en la secuencia no es código de este repo. Se muestra para ubicar el webhook.

## Cómo se rehacen

El modelo del explicador está en [como-funciona.legibify.json](como-funciona.legibify.json). Se regenera con `node player/build.mjs como-funciona.legibify.json como-funciona.html`, usando el player de legibify. Los diagramas `.html` y `.svg` están dibujados a mano con la paleta del equipo (crema `#fff7ec`, tinta `#1d1a16`, rosa `#e8457a`, verde `#1f8a5b`) y las fuentes Bricolage Grotesque e Inter.
