# Página del puesto, libreta y landing

Estado: alcance posterior al hackatón. El corte sigue siendo WhatsApp, como dice `00-plataforma.md`.

La puerta sigue siendo WhatsApp. Estas páginas no son otra app: son la cara pública del puesto, la libreta del dueño y la landing del pitch. Depende de `05-multitenant.md`. No hay cuentas de usuario ni contraseñas en ninguna.

## Página del puesto

Cada puesto tiene una URL pública y estable. Es la misma URL que lleva la pegatina NFC de `03-nfc.md`. Abrir la página no arma ni crea cobros: muestra el nombre del puesto y el último QR que el dueño armó desde el chat, con la confirmación de `G04`. Si el dueño no ha armado un QR, la página muestra solo el nombre. El dueño arma desde el chat el QR del monto fijo del puesto o, si deja un monto para un cobro suelto, el de ese monto; quien visita la página no escribe montos. Nunca se muestra la CLABE ni el teléfono del dueño.

## Libreta

El dueño pide su libreta por WhatsApp y el bot le manda un link de un solo uso, con un token aleatorio de al menos 128 bits y vencimiento de 15 minutos. La libreta lista los pagos de su puesto con monto, concepto, fecha y totales. No hay score de crédito: sigue valiendo `NG-3`.

## Landing

Una página pública para el pitch: qué es Varísimo y qué se vio en la demo. Sin cuentas ni contraseñas.

## Criterios

REQ-32. WHILE alguien abre la página de un puesto, THE página SHALL mostrar el nombre del puesto y el último QR que el dueño armó desde el chat, y SHALL NOT llamar a pey ni crear un cobro por abrirla.

Evidencia: abrir la página de un puesto de prueba no genera ningún `POST /codi/qr`. Si el dueño ya armó un QR, el HTML trae ese QR; si no, trae solo el nombre del puesto.

REQ-33. WHILE el dueño escribe en el chat un monto para un cobro suelto y lo confirma con el código de `G04`, THE bot SHALL armar el QR con ese monto, dentro del tope, y THE página SHALL mostrarlo, y SHALL NOT dejar el monto abierto en cero.

Evidencia: un monto dentro del tope, confirmado con el código, genera el QR con ese monto y la página lo muestra. Sin el código, cero o un monto mayor que el tope no llaman a pey.

REQ-34. WHILE la página de un puesto se muestra, THE página SHALL NOT mostrar la CLABE ni el teléfono del dueño.

Evidencia: el HTML servido de un puesto de prueba no trae la CLABE del puesto ni el número del dueño.

REQ-35. WHILE el dueño pide su libreta, THE bot SHALL mandarle por WhatsApp un link de un solo uso con un token aleatorio de al menos 128 bits y vencimiento de 15 minutos, que abre la libreta de su puesto.

Evidencia: el link abierto una vez deja de servir, uno vencido no abre, el token de prueba tiene al menos 128 bits y no pide usuario ni contraseña.

REQ-36. WHILE la libreta se abre, THE libreta SHALL listar los pagos del puesto con monto, concepto, fecha y totales, y SHALL NOT mostrar un score de crédito.

Evidencia: la libreta de un puesto de prueba suma los pagos del registro y no trae ningún score.

REQ-37. WHILE alguien abre la landing del pitch, THE página SHALL mostrar el nombre del producto, qué resuelve (cobrar con CoDi desde WhatsApp, con texto, voz y foto de ticket) y qué se vio en la demo, y SHALL NOT pedir datos para mostrarse.

Evidencia: el HTML servido de la landing de prueba trae el nombre del producto, la propuesta y la sección de la demo.

REQ-38. THE sistema SHALL NOT pedir usuario ni contraseña en la página del puesto, en la libreta ni en la landing.

Evidencia: ninguna de las tres páginas pide credenciales.

## No entra aquí

- NG-15. Un catálogo o una tienda en línea. La página del puesto es su nombre y su cobro.
- NG-16. Cuentas de usuario o contraseñas. El acceso del dueño a la libreta es el link de un solo uso.
- NG-20. Armar un QR al abrir la página. El QR lo arma el dueño desde el chat, con la confirmación de `G04`; la página solo muestra el último armado o nada.
