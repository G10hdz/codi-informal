# Requerimientos

La meta no es el repositorio. Es esto desplegado y usable.

Usable quiere decir que Altagracia, sin que nadie le dicte la pantalla, puede en WhatsApp:

1. Pedir un cobro de $0.01 a un celular de 10 dígitos y que a esa persona le llegue el push de CoDi en su banco.
2. Pedir el QR del puesto y recibirlo en el chat.
3. Mandar una nota de voz con la misma orden y que el bot la entienda.
4. Mandar la foto de un ticket y que el bot le diga monto y concepto antes de cobrar.
5. Recibir ella, o el dueño, un mensaje cuando el pago entra, sin foto de comprobante y sin llamada.

Eso tiene que ocurrir en un URL público, con la API key de pey y el número de WhatsApp del equipo. Mientras falte una de las dos llaves, el flujo local cuenta como esqueleto, no como terminado.

El detalle medible está en `specs/`. El orden para llegar ahí está en `specs/roadmap.md`.
