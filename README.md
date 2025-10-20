# BeatBetano (React + Vite) v1.2.2

**Cambio clave:** `vite.config.js` ahora usa `base: '/BeatBetano/'` (coincide con el nombre del repo con B mayúscula).
Incluye página de diagnóstico `/env` que muestra `import.meta.env.BASE_URL` en producción.

## Deploy (GitHub Pages - Actions)
1. Sube este proyecto al repo `amante/BeatBetano` (mismo case).
2. Settings → Pages → Source: **GitHub Actions**.
3. Push a `main` y el workflow publicará `dist/`.

## Dev local
```bash
npm install
npm run dev
```