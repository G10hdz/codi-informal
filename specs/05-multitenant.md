# Varios puestos

El corte del hackatón es un puesto y un dueño: `OWNER_WHATSAPP`. Este spec abre el bot a varios puestos, cada uno con su dueño, su cuenta de pey y sus límites. Depende de `01-whatsapp-codi.md` y de los guardrails (`G01`, `G04`, `G07`).

## Qué cambia

Cada puesto es una entrada del registro local: el número del dueño, el `bankAccountId` de pey y los límites. Las operaciones y los pagos quedan marcados con el puesto que los creó. El dueño de un puesto solo ve y confirma lo suyo. Un número que no es dueño de ningún puesto no llega a ningún camino de cobro.

El alta de un puesto la hace un operador, fuera del chat. En este corte no hay autoservicio: un mensaje que pida un puesto no crea nada.

El bloqueo de cobros inciertos deja de ser global: un cobro sin respuesta de pey detiene solo al puesto dueño del cobro.

## Criterios

REQ-23. WHILE el sistema atiende a varios puestos, THE sistema SHALL guardar por puesto el número del dueño, el `bankAccountId` y los límites, y SHALL marcar cada operación y cada pago con el puesto que los creó.

Evidencia: dos puestos cargados. Una operación de A no aparece en el registro de B y no consume el cupo de B.

REQ-24. WHILE un mensaje llega de un número que no es dueño de ningún puesto, THE sistema SHALL ignorarlo antes de transcribir o llamar a pey y SHALL NOT abrir un camino de cobro.

Evidencia: un remitente ajeno no consume transcripción y no llama a `POST /codi/pn`.

REQ-25. WHILE un dueño pregunta qué se ha cobrado, THE sistema SHALL responder solo con los pagos de su puesto.

Evidencia: A y B preguntan lo mismo y reciben registros distintos, cada uno el suyo.

REQ-26. WHILE un dueño confirma un borrador de cobro, THE sistema SHALL validar que el borrador es de su puesto antes de llamar a pey, además del monto y el vencimiento de `G04`.

Evidencia: la confirmación de A presentada desde el chat de B no ejecuta nada.

REQ-27. WHILE un puesto se da de alta, THE sistema SHALL exigir a un operador registrar el número del dueño, la cuenta y los límites fuera del chat. Un mensaje no da de alta un puesto.

Evidencia: el texto "dame un puesto" recibe una negativa y no crea entradas.

REQ-28. WHILE el `bankAccountId` de un puesto no está en `ACTIVE`, THE sistema SHALL NOT cobrar para ese puesto con esa cuenta.

Evidencia: un puesto con cuenta `PENDING` no llega a pey y recibe un aviso de que el cobro no salió.

REQ-29. WHILE un cobro de un puesto queda incierto, THE sistema SHALL bloquear cobros nuevos solo de ese puesto. Los demás puestos siguen cobrando.

Evidencia: un timeout en un cobro de A no detiene un cobro de B.

REQ-30. THE sistema SHALL NOT guardar la CLABE de ningún puesto, ni cuando el webhook `bank.account.updated` la traiga.

Evidencia: el registro de prueba con dos puestos no contiene CLABEs.

REQ-31. WHILE el bot usa un número de sandbox que solo atiende a los teléfonos registrados en el proveedor, THE sistema SHALL NOT dar de alta más dueños de los que ese número puede atender.

Evidencia: con el sandbox de Kapso (un teléfono), el alta de un segundo dueño se rechaza.

## El número de WhatsApp

El sandbox de Kapso responde a un solo teléfono registrado. Varios dueños escribiéndole al mismo bot piden un número de WhatsApp verificado, que responda a cualquier teléfono. Dar de alta una línea mexicana para el bot pide CURP e INE de quien la registra. Hasta que ese número exista, el bot sigue siendo de un dueño, como dice REQ-31.

## No entra aquí

- NG-13. Alta de puestos por autoservicio o desde el chat. La hace un operador fuera del chat.
- NG-14. Cobrar para un puesto con la cuenta de otro, o con una cuenta que no esté en `ACTIVE`.
