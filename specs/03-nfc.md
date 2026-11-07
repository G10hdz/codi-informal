# NFC

El tap no es un tercer sistema de pagos. Identifica el puesto y abre el cobro que ya existe.

pey, en el OpenAPI 2026-10-20, documenta QR y push. No documenta un endpoint NFC. Este spec no agrega uno.

## Criterios

REQ-16. WHILE un tap trae el id de un puesto, THE sistema SHALL iniciar el mismo cobro que el QR de ese puesto: monto dentro del tope, concepto del puesto, y aviso al dueño cuando pey confirme el pago.

Evidencia: un tap de prueba con `puesto=tacos` produce la misma orden que `manda el qr` de ese puesto. No aparece un path distinto de `/codi/qr` o `/codi/pn`.

REQ-17. WHILE el tap no trae un puesto conocido, THE sistema SHALL decir que no reconoce el puesto y SHALL NOT cobrar.

Evidencia: un id que no está en el registro local no llama a pey.

REQ-18. WHILE el teléfono no tiene NFC o la persona no puede usarlo, THE puesto SHALL seguir cobrando con el QR y con el push. El tap es un atajo, no la única puerta.

Evidencia: REQ-1 y REQ-3 siguen pasando sin un lector NFC.

## No entra aquí

- NG-4. Llamar a pey por un endpoint NFC que no esté en `docs/pey-api.md`.
- NG-10. Guardar el identificador del teléfono de quien acerca el aparato.
