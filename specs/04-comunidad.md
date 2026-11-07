# Economía de comunidad

Misma capa de CoDi. No es otra app de tandas ni otro QR.

El dato de escala es el de `00-plataforma.md`: 33.1 millones de personas en la informalidad, 55.1% de la población ocupada (INEGI, ENOE, segundo trimestre de 2026). La comunidad ya resuelve mandado, tandas y compras entre vecinos. Alguien del equipo armó esa red en una plaza. El tianguis es el siguiente lugar, no un producto distinto.

## Tanda

REQ-19. WHILE una tanda tiene integrantes, monto y calendario, THE sistema SHALL cobrar a cada quien con el mismo push de REQ-1 y SHALL NOT dejar el dinero en manos de una persona administradora.

Evidencia: tres cobros de prueba quedan en el registro con el id de la tanda. No hay un saldo que alguien pueda retirar fuera de CoDi.

REQ-20. WHILE un integrante no paga en la fecha, THE sistema SHALL avisarlo por WhatsApp y SHALL NOT marcar la tanda como completa.

Evidencia: un calendario de prueba con un pago faltante no cambia el estado a completa.

## Compras entre puestos y entre vecinos

REQ-21. WHILE varios puestos piden el mismo producto, THE bot SHALL reunir el pedido y SHALL NOT cobrar de más a cada quien por encima de su parte, dentro del tope de prueba.

Evidencia: dos puestos piden el mismo insumo. El registro muestra dos montos que suman el total, no el total repetido dos veces.

REQ-22. WHILE un punto comunitario recibe un mandado, THE aviso de pago SHALL llegar al punto y a quien pidió, por WhatsApp, cuando pey confirme.

Evidencia: un webhook de ese cobro genera dos textos de aviso y una sola fila en el registro.

## No entra en el hackatón

- NG-11. Construir la tanda, la compra colectiva y la red de puntos antes del domingo 8 de noviembre de 2026, 1:00 p.m.
- NG-12. Duplicar una app de tandas o un QR genérico que no deje registro.
