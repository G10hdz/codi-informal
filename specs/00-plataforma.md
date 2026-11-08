# Plataforma para la economía informal y de comunidad

Estado: propuesta para el equipo. El corte del hackatón está en `01-whatsapp-codi.md`. Lo demás no se construye hasta que este archivo y el plan de esa fase estén aceptados.

## Para quién

33.1 millones de personas trabajan en la informalidad. Son el 55.1% de la población ocupada, según el INEGI (ENOE, segundo trimestre de 2026). Más de la mitad del país.

El primer uso es el puesto de tianguis y la tanda. El siguiente es la economía de comunidad: compras entre vecinos, mandado y puntos que ya existen en una plaza y se pueden extender al tianguis.

Quien cobra a veces no sabe escribir, o no quiere instalar otra app. Habla, manda una nota de voz o una foto del ticket. Quien prueba los flujos con esa mirada es Altagracia.

## Qué es

Una capa de pagos con CoDi. La puerta es un agente en WhatsApp. No hay frontend en el corte del hackatón. Las páginas del puesto, la libreta y la landing quedan definidas en `06-front.md` como alcance posterior al hackatón.

El agente entiende texto, voz y una foto. Contesta en el idioma del mensaje. Con eso arma un push de CoDi, un QR para dejar pegado, o el registro de un pago que ya entró. Un tap NFC, cuando el puesto lo tenga, abre el mismo cobro. No es otro riel.

## Hecho

Está hecho cuando Altagracia completa, en el WhatsApp desplegado, los cinco pasos de `REQUERIMIENTOS.md`. El repositorio solo no cuenta.

## Fuera de este producto

- NG-1. Una página o una app para instalar dentro del corte del hackatón. Las páginas de `06-front.md` son alcance posterior al hackatón.
- NG-2. Dar de alta al comercio en el SAT.
- NG-3. Un score de crédito. El registro es el primer paso, no el crédito.
- NG-4. Un endpoint de NFC que pey no documenta. El tap usa el mismo push o el mismo QR.
- NG-5. Guardar CLABEs, la foto cruda del ticket o el secreto del webhook.
