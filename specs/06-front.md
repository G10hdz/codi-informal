# Página del puesto, libreta y landing

La puerta sigue siendo WhatsApp. Estas páginas no son otra app: son la cara pública del puesto, la libreta del dueño y la landing del pitch. Depende de `05-multitenant.md`. No hay cuentas de usuario ni contraseñas en ninguna.

## Página del puesto

Cada puesto tiene una URL pública y estable. Es la misma URL que lleva la pegatina NFC de `03-nfc.md`. Muestra el nombre del puesto y un QR de CoDi armado al momento, con el monto fijo del puesto, dentro del tope. Si el dueño deja primero un monto para un cobro suelto, el QR sale con ese monto; quien visita la página no escribe montos. Nunca se muestra la CLABE ni el teléfono del dueño.

## Libreta

El dueño pide su libreta por WhatsApp y el bot le manda un link de un solo uso. La libreta lista los pagos de su puesto con monto, concepto, fecha y totales. No hay score de crédito: sigue valiendo `NG-3`.

## Landing

Una página pública para el pitch: qué es Varísimo y qué se vio en la demo. Sin cuentas ni contraseñas.

## Criterios

REQ-32. WHILE alguien abre la página de un puesto, THE página SHALL mostrar el nombre del puesto y un QR de CoDi armado al momento, con el monto fijo del puesto dentro del tope.

Evidencia: abrir la página de un puesto de prueba genera un `POST /codi/qr` con el monto fijo y muestra el `qrString` que respondió pey.

REQ-33. WHILE el dueño deja primero un monto para un cobro suelto, THE página SHALL armar el cobro con ese monto, dentro del tope, y SHALL NOT dejar el monto abierto en cero.

Evidencia: un monto dentro del tope genera el QR con ese monto. Cero o un monto mayor que el tope no llaman a pey.

REQ-34. WHILE la página de un puesto se muestra, THE página SHALL NOT mostrar la CLABE ni el teléfono del dueño.

Evidencia: el HTML servido de un puesto de prueba no trae la CLABE del puesto ni el número del dueño.

REQ-35. WHILE el dueño pide su libreta, THE bot SHALL mandarle por WhatsApp un link de un solo uso que abre la libreta de su puesto.

Evidencia: el link abierto una vez deja de servir, y no pide usuario ni contraseña.

REQ-36. WHILE la libreta se abre, THE libreta SHALL listar los pagos del puesto con monto, concepto, fecha y totales, y SHALL NOT mostrar un score de crédito.

Evidencia: la libreta de un puesto de prueba suma los pagos del registro y no trae ningún score.

REQ-37. WHILE alguien abre la landing del pitch, THE página SHALL presentar el producto y la demo.

REQ-38. THE sistema SHALL NOT pedir usuario ni contraseña en la página del puesto, en la libreta ni en la landing.

Evidencia: ninguna de las tres páginas pide credenciales.

## No entra aquí

- NG-15. Un catálogo o una tienda en línea. La página del puesto es su nombre y su cobro.
- NG-16. Cuentas de usuario o contraseñas. El acceso del dueño a la libreta es el link de un solo uso.
