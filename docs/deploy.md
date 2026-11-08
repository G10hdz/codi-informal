# Deploy en somas-vps

El bot corre en un contenedor `codi-informal` (imagen `python:3.13-slim`, sin build). El código se monta de solo lectura y SQLite vive en un directorio aparte.

| Qué | Dónde |
|---|---|
| URL pública | `https://codi.169.58.159.184.sslip.io` |
| Código | `/opt/codi-informal/app/codi_informal` |
| Variables | `/opt/codi-informal/.env` (permisos 600) |
| Registro y límites | `/opt/codi-informal/data` |
| Puerto local | `127.0.0.1:3320`, detrás de Caddy (`/etc/caddy/Caddyfile`) |

Webhooks a registrar:

- WhatsApp (Meta o Kapso): `https://codi.169.58.159.184.sslip.io/webhooks/whatsapp`
- pey: `https://codi.169.58.159.184.sslip.io/webhooks/pey`

## Subir una versión nueva

Desde un checkout de `main` actualizado:

```bash
rsync -a --delete --exclude '__pycache__' codi_informal/ root@somas-vps:/opt/codi-informal/app/codi_informal/
ssh root@somas-vps 'docker restart codi-informal && docker logs --tail 3 codi-informal'
curl -s https://codi.169.58.159.184.sslip.io/health
```

## Cambiar llaves

```bash
ssh root@somas-vps
nano /opt/codi-informal/.env
docker restart codi-informal
```

El arranque imprime `pey=sin key` mientras falte `PEY_API_KEY`.

## Pausar cobros

`COBROS_ACTIVOS=0` en el `.env` y reiniciar el contenedor. Los pagos que ya venían se siguen conciliando.

## Cobro en duda

Si pey no contesta a tiempo, el cobro queda incierto y bloquea cobros nuevos. Revisarlo en el portal de pey y cerrarlo:

```bash
ssh root@somas-vps 'docker exec codi-informal python -m codi_informal.registro'
ssh root@somas-vps 'docker exec codi-informal python -m codi_informal.registro resolver <op_id> fallida'
```

Usar `creada` en vez de `fallida` si pey sí lo creó.
