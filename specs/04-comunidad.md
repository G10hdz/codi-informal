# Economía de comunidad

Misma capa de CoDi. No es otra app de tandas ni otro QR.

El dato de escala es el de `00-plataforma.md`: 33.1 millones de personas en la informalidad, 55.1% de la población ocupada (INEGI, ENOE, segundo trimestre de 2026). La comunidad ya resuelve mandado, tandas y compras entre vecinos. Alguien del equipo armó esa red en una plaza. El tianguis es el siguiente lugar, no un producto distinto.

## Tanda

Las reglas de la tanda son concretas: quiénes son integrantes, el monto por integrante, el orden de turnos y el calendario de fechas. Cada integrante tiene su propia cuenta de pey. El sistema cobra a cada quien con un push en su fecha y le recuerda por WhatsApp a quien no ha pagado. Quien tiene el turno recibe directo en su cuenta; nadie junta ni guarda un bote.

La tanda pertenece al puesto de `05-multitenant.md` que la arma, y el dueño de ese puesto es su organizador. Cada integrante preautoriza su propio cobro al unirse, con el código de confirmación de un solo uso de `G04`; sin esa preautorización no hay cobro.

REQ-19. WHILE una tanda tiene integrantes, monto y calendario, THE sistema SHALL cobrar a cada quien con el mismo push de REQ-1 y SHALL NOT dejar el dinero en manos de una persona administradora.

Evidencia: tres cobros de prueba quedan en el registro con el id de la tanda. No hay un saldo que alguien pueda retirar fuera de CoDi.

REQ-20. WHILE un integrante no paga en la fecha, THE sistema SHALL avisarlo por WhatsApp y SHALL NOT marcar la tanda como completa.

Evidencia: un calendario de prueba con un pago faltante no cambia el estado a completa.

REQ-41. WHILE una tanda se arma, THE tanda SHALL tener integrantes, monto, orden de turnos y calendario, y cada integrante SHALL tener su propia cuenta de pey en `ACTIVE`.

Evidencia: una tanda de prueba con tres integrantes carga el orden y el calendario, y no se arma sin una cuenta activa por integrante.

REQ-42. WHILE llega la fecha de un integrante que preautorizó su cobro, THE sistema SHALL cobrarle el monto de la tanda con el mismo push de REQ-1, a su celular, y SHALL NOT cobrar a quien no preautorizó.

Evidencia: el calendario de prueba dispara el cobro del integrante en su fecha, con la orden que produce `cobra <monto> al <teléfono>`, y no dispara el de un integrante sin preautorización.

REQ-43. WHILE un integrante no ha pagado, THE sistema SHALL mandarle por WhatsApp como máximo un recordatorio al día, hasta que pague o el organizador de la tanda lo detenga desde su chat. El aviso de REQ-20 sigue valiendo.

Evidencia: un integrante de prueba sin pagar recibe como máximo un recordatorio al día; la orden del organizador los detiene y ninguno cobra de más.

REQ-44. WHILE se cobra a un integrante, THE dinero SHALL caer directo en la cuenta del integrante que tiene el turno, con su `bankAccountId`, y SHALL NOT pasar por una cuenta común ni por un administrador.

Evidencia: el push de prueba va a la cuenta de quien tiene el turno y no existe una cuenta que retenga dinero.

REQ-45. WHILE un integrante no paga, THE sistema SHALL NOT cobrarle penas ni intereses y SHALL avisar a la tanda para que el grupo decida qué hacer.

Evidencia: el integrante que no paga no recibe un cargo extra; el aviso lo nombra y deja la decisión al grupo.

REQ-49. WHILE una tanda se arma, THE sistema SHALL pedir a cada integrante que preautorice su propio cobro con el mismo código de confirmación de un solo uso que el chat, ligado a él, a su monto y a su fecha.

Evidencia: un integrante de prueba confirma su alta con un código que solo vale para él; el código de otro integrante no autoriza su cobro.

REQ-50. WHILE una tanda cobra, THE sistema SHALL resolver la operación con el puesto dueño de la tanda y con la cuenta de pey del integrante que paga, y SHALL NOT cobrar con la cuenta de otro puesto ni con la de otro integrante.

Evidencia: un cobro de una tanda de prueba queda marcado con el puesto que la armó; presentar la cuenta de otro integrante como pagador no llama a pey.

## Compras entre puestos y entre vecinos

REQ-21. WHILE varios puestos piden el mismo producto, THE bot SHALL reunir el pedido y SHALL NOT cobrar de más a cada quien por encima de su parte, dentro del tope de prueba.

Evidencia: dos puestos piden el mismo insumo. El registro muestra dos montos que suman el total, no el total repetido dos veces.

REQ-22. WHILE un punto comunitario recibe un mandado, THE aviso de pago SHALL llegar al punto y a quien pidió, por WhatsApp, cuando pey confirme.

Evidencia: un webhook de ese cobro genera dos textos de aviso y una sola fila en el registro.

## No entra aquí

- NG-11. Construir la tanda, la compra colectiva y la red de puntos antes del domingo 8 de noviembre de 2026, 1:00 p.m.
- NG-12. Duplicar una app de tandas o un QR genérico que no deje registro.
- NG-18. Penas, intereses o cargos automáticos para quien no paga. Lo que pasa con un atraso lo decide el grupo.
