# Voz, idiomas y lectura de tickets

El mismo agente de `01-whatsapp-codi.md`. No es otro canal con otra lógica de cobro.

## Voz

REQ-8. WHILE llega una nota de voz y hay transcriptor, THE bot SHALL pasar el texto resultante por el mismo interpretador que un mensaje escrito.

Evidencia: un doble de transcriptor que devuelve `cobra 0.01 al 5512345678` produce la misma orden que ese texto.

REQ-9. WHILE llega una nota de voz y no hay transcriptor, THE bot SHALL pedir la orden escrita y SHALL NOT inventar un monto.

Evidencia: la respuesta fija de `atender` cuando `transcribir` es nulo.

REQ-10. WHILE el equipo enciende un agente de voz en vivo, THE agente SHALL usar las mismas órdenes que el chat: cobrar, pedir el QR y preguntar qué se ha cobrado. No verifica identidad ante Banxico.

Evidencia: las frases de voz caen en `Agente.responder`. pey no documenta un endpoint de identidad.

## Idiomas

REQ-11. WHILE el mensaje viene en un idioma distinto del español y el detector está seguro, THE bot SHALL contestar en ese idioma.

Evidencia: un fixture en español y uno en inglés. La orden parseada es la misma. Cambia el texto de la respuesta, no el cuerpo que se manda a pey.

REQ-12. WHILE el idioma no se reconoce, THE bot SHALL contestar en español.

Evidencia: un texto ambiguo recibe la ayuda en español.

## Foto del ticket

Hoy, si el dueño no está, el comprobante es una foto. El agente la lee para no dejarla como único registro.

REQ-13. WHILE llega una imagen de ticket, THE bot SHALL decir el monto y el concepto que leyó y SHALL NOT cobrar hasta un sí de la persona.

Evidencia: una imagen de prueba con un total visible. La respuesta trae ese total y ninguna llamada a `POST /codi/pn` antes de la confirmación.

REQ-14. WHILE la persona confirma el monto leído, THE bot SHALL seguir REQ-1 o negarse por REQ-2.

Evidencia: el sí reusa el cobro push. El no no llama a pey.

REQ-15. THE sistema SHALL NOT guardar la imagen del ticket ni un número de cuenta que aparezca en ella.

Evidencia: el registro de esa prueba solo tiene monto, concepto y, si ya se cobró, `transactionId`.

## No entra aquí

- NG-8. Prometer lectura perfecta de cualquier ticket. Si el monto no se lee, se pregunta.
- NG-9. Un modelo de voz propio. Se usa el transcriptor que esté configurado.
