# IP Shakti frontend

## Local development

Set `BACKEND_URL` in `.env` to the backend origin (default:
`http://localhost:8080`). Then run:

```sh
npm ci
npm run dev
```

The frontend is split into route pages, reusable UI components, and API/auth
helpers under `src/`. Run `npm run lint` and `npm run build` to validate changes.

For Render deployment settings, see the backend
[HELP.md](../Ip-Shakti_Backend/HELP.md#deploying-on-render).
