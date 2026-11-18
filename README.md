# SIGI CRM Institucional

Frontend y backend del CRM institucional para gestionar proyectos, solicitudes, tareas, documentos, soporte y notificaciones ntfy.

## Ejecutar

Desde esta carpeta:

```powershell
python server.py
```

Abrir http://127.0.0.1:4173/.

Credenciales demo:

- Usuario: `admin@sigi.local`
- Contraseña: `admin123`

El servidor ntfy de desarrollo debe estar disponible en http://127.0.0.1:2586/.

## Instrucciones para agentes de desarrollo

Si Codex, Claude Code u otro agente recibe este repositorio, debe:

1. Leer primero `README.md`, `index.html`, `app.js`, `styles.css`, `functional.css` y `server.py`.
2. No borrar ni recrear `sigi.db` sin autorización; contiene datos locales de desarrollo.
3. No subir `sigi.db`, contraseñas, tokens, archivos `.env` ni credenciales de ntfy.
4. Levantar el CRM con `python server.py` y abrir http://127.0.0.1:4173/.
5. Comprobar primero login y dashboard antes de modificar código.
6. Mantener SQLite y ntfy salvo que se solicite explícitamente otra arquitectura.
7. Después de modificar `app.js`, ejecutar `node --check app.js`.
8. Verificar login, dashboard, proyectos, solicitudes, Kanban, administración, documentos, calendario, soporte, reportes y notificaciones.
9. Explicar en cada commit qué cambió y qué pruebas se ejecutaron.

### Arquitectura

- `server.py`: API local, autenticación, SQLite, permisos, auditoría y ntfy.
- `sigi.db`: base local; no debe versionarse.
- `index.html`: entrada del frontend.
- `app.js`: módulos, navegación, formularios y API.
- `styles.css` y `functional.css`: estilos y responsive.
- `ntfy-oficialia`: servidor ntfy compilado desde el código fuente y desplegado con Docker.

### Seguridad antes de producción

Cambiar las credenciales demo, definir `SIGI_NTFY_USER` y `SIGI_NTFY_PASSWORD`, usar HTTPS, respaldar SQLite, revisar permisos por rol y no guardar secretos en el código.
