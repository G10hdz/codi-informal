# API de pey que usa este repo

Fuente: OpenAPI 3.1.1 con fecha 2026-10-20, en https://docs.pey.mx/openapi.json, más las páginas de webhooks de https://docs.pey.mx. Si la doc cambia, esta nota hay que volver a sacarla de ahí. No inventes campos que aquí no estén.

## Base y acceso

- Base: `https://api.pey.mx`
- Header: `Authorization: Bearer <api key>`
- La key se crea en el portal, en Desarrollador, y se liga a una cuenta de pago. Cada key puede tener una cuenta CoDi y una de Stripe. Para este corte basta la de CoDi.
- El correo del hackatón dice https://portal.pey.mx. La doc de pey dice https://portal.mipey.mx. El webhook se registra en https://portal.mipey.mx/developers
- No hay ambiente de prueba. Se cobra en producción. Los pagos no se devuelven. El bot, si no le cambian `PEY_MAX_AMOUNT`, no pasa de $0.01.
- Las CLABEs de prueba están en el correo "INSTRUCCIONES Y PREMIOS" y en la guía de pey. No van en git.

## Push

`POST /codi/pn`

pey le manda a Banxico una notificación de cobro al celular de quien paga.

Obligatorios:

- `amount`: número en MXN, mayor que 0 y hasta 1,000,000
- `phoneNumber`: 10 dígitos, sin 52

Opcionales:

- `concept`: texto que ve quien paga
- `expiration`: segundos, mínimo 360. Si no se manda, pey usa 360.
- `numRef`: solo dígitos, máximo 7
- `bankAccountId`: ULID de una cuenta con `codiStatus` en `ACTIVE`. Si no va, el dinero cae en la cuenta ligada a la API key.
- `metadata`: hasta 50 pares. La llave mide hasta 40 caracteres y el valor hasta 500. Solo escalares (texto, número, booleano o null). pey los guarda como texto.

Respuesta 200:

- `transactionId`: ULID interno para seguir el pago
- `codiId`: folio de Banxico, 20 dígitos

## QR

`POST /codi/qr`

Obligatorio: `amount`, en MXN, desde 0. Cero quiere decir que quien escanea escribe el monto. Este repo no manda cero: en una cuenta de prueba esa persona podría poner cualquier cantidad, y el pago no se devuelve.

Opcionales: `concept`, `expiration`, `numRef`, `generateImage`, `bankAccountId`, `metadata`.

`expiration` en 0 no vence. Si es mayor que 0, el mínimo es 360 segundos.

`generateImage: true` pide `qrImage`, un PNG en base64. La respuesta tarda más. Si no hace falta la imagen, se arma el QR en el cliente con `qrString`.

Respuesta 201:

- `id`: IDC que asigna Banxico
- `qrString`: el contenido del QR
- `qrImage`: PNG en base64, o null si no se pudo dibujar. El QR igual queda creado.

## Cuenta bancaria

`POST /bank-account`

Obligatorios: `alias`, `name` (nombre legal), `clabe` de 18 dígitos con dígito verificador válido y banco con CoDi, `entity` en `BUSINESS` o `PERSON`.

La cuenta nace en `PENDING`. pey la registra con Banxico y pasa a `ACTIVE`. Puede tardar hasta 5 días hábiles. Solo una cuenta `ACTIVE` se puede usar como `bankAccountId`. Mientras tanto se omite `bankAccountId` y se usa la cuenta ya ligada a la API key.

`GET /bank-account/{id}` devuelve `codiStatus`: `PENDING`, `PROCESSING`, `ACTIVE` o `ERROR`. En `ERROR` viene `errorMessage`.

Cuando pasa a `ACTIVE`, pey manda el webhook `bank.account.updated`. Ese cuerpo trae la CLABE. Este repo responde 200 y no la guarda.

## Consultar un pago

`GET /transaction/{id}`

- `status`: `PENDING` o `PAID`
- `paymentMethod`: `CARD` o `CODI`
- `payableType`: `PAYMENT_LINK`, `API_CODI_QR` o `API_CODI_PN`
- `datePaid`: unix en segundos, solo si ya se pagó

Un QR no es una transacción. Sus pagos van en `GET /transaction/codi/qr/{id}`, de 20 en 20.

`GET /transaction/api-key` lista lo recibido por la key, de 80 en 80, lo más nuevo primero. La query `nextToken` pide la siguiente página. La key sale del header, no del path.

`GET /transaction/bank-account/{id}` lista los pagos de una cuenta registrada, también de 80 en 80.

## Webhooks

Una API key tiene un solo webhook. Se da de alta en el portal, en el engrane de la key, y ahí se copia el secreto.

pey firma con [Standard Webhooks](https://www.standardwebhooks.com/).

Headers:

- `webhook-id`: también sirve para no procesar dos veces el mismo envío
- `webhook-timestamp`: unix en segundos. Si tiene más de 5 minutos, se rechaza.
- `webhook-signature`: una o varias firmas `v1,<base64>`, separadas por espacio

El contenido firmado es `webhook-id.webhook-timestamp.` más el cuerpo crudo, en bytes, sin volver a serializar el JSON. El secreto es la parte de después de `whsec_`, en base64. La comparación tiene que ser en tiempo constante.

Eventos que este repo atiende:

- `codi.pn.payment_received`
- `codi.qr.payment_received`
- `bank.account.updated`

En un pago vienen `amount`, `concept`, `datePaid`, `numRef`, `transactionId` y `type`. El de QR trae `codiQrId`. El de push puede traer `bankAccountId` y `metadata`. Dentro de `metadata` a veces viene `clabe` y, en `externalMetadata`, los pares que mandamos al crear el cobro. La CLABE no se escribe en el registro.

Los estados `PENDING`, `PROCESSING` y `ERROR` de una cuenta no disparan webhook. Esos se consultan con `GET /bank-account/{id}`.

## Errores

Cuerpo típico: `{"error": {"message": "...", "type": "..."}}`.

- 400: parámetro inválido o campo faltante
- 404: el id no existe o es de otra API key
- 500: error interno
- 503: el endpoint está en mantenimiento

## Lo que la doc tiene y este corte no usa

`/payment-link/create`, `/payment-link/update` y `/payment-link/{id}` abren un checkout hospedado de CoDi, tarjeta, Apple Pay y Google Pay. El corte es el bot de WhatsApp, no esa página.
