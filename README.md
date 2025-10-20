# BeatBetano (React + Vite) v1.2.1

Fix de deploy para GitHub Pages:
- Workflow usa `npm install` (evita fallo cuando no hay `package-lock.json`).
- Config mantiene `base: '/beatbetano/'` y copia `404.html` al build.

## Deploy
1. Sube todo este proyecto al repo `amante/beatbetano`.
2. En Settings → Pages, `Source = GitHub Actions`.
3. Push a `main` y espera a que el workflow publique en `https://amante.github.io/beatbetano/`.

## Desarrollo local
```bash
npm i
npm run dev
```