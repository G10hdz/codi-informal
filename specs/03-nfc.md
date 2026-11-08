# NFC

La pegatina NTAG del puesto lleva una URL: la página pública del puesto de `06-front.md`. El tap abre esa página en el navegador y el cobro que ya existe se hace ahí, con el QR de `01-whatsapp-codi.md`. El tap no es un tercer sistema de pagos.

pey, en el OpenAPI 2026-10-20, documenta QR y push. No documenta un endpoint NFC. Este spec no agrega uno: la pegatina no habla con pey.

## Criterios

REQ-16. WHILE un tap trae la URL de un puesto, THE teléfono SHALL abrir la página de ese puesto y THE sistema SHALL iniciar el mismo cobro que el QR del puesto: monto dentro del tope, concepto del puesto, y aviso al dueño cuando pey confirme el pago.

Evidencia: un tap de prueba con la URL del puesto `tacos` termina en el mismo cobro que `manda el qr` de ese puesto. No aparece un path distinto de `/codi/qr` o `/codi/pn`.

REQ-17. WHILE el tap trae una URL que no es de un puesto conocido, THE sistema SHALL decir que no reconoce el puesto y SHALL NOT cobrar.

Evidencia: una URL que no está en el registro local no llama a pey.

REQ-18. WHILE el teléfono no tiene NFC o la persona no puede usarlo, THE puesto SHALL seguir cobrando con el QR y con el push. El tap es un atajo, no la única puerta.

Evidencia: REQ-1 y REQ-3 siguen pasando sin un lector NFC.

REQ-39. WHILE se escribe una pegatina NTAG para un puesto, THE pegatina SHALL llevar solo la URL pública del puesto y SHALL NOT llevar CLABE, teléfono ni llave.

Evidencia: lo que se graba en una pegatina de prueba es una URL y nada más.

REQ-40. WHILE la URL del puesto no cabe en la memoria de la pegatina, THE sistema SHALL usar una URL corta que abra la misma página.

Evidencia: la URL del puesto de prueba cabe en un NTAG213.

## No entra aquí

- NG-4. Llamar a pey por un endpoint NFC que no esté en `docs/pey-api.md`.
- NG-10. Guardar el identificador del teléfono de quien acerca el aparato.
- NG-17. Una app propia para leer la pegatina. El tag es una URL estándar que abre el navegador del teléfono.
