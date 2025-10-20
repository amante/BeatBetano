# BeatBetano (React + Vite) v1.2.3

- `index.html` usa `<script src="/src/main.jsx">` (ruta absoluta) para que Vite **reescriba** a `assets/*.js` en el build.
- Workflow oficial de GitHub Pages con `configure-pages` y pasos de diagnóstico que muestran la cabecera de `dist/index.html` y hacen `grep` para verificar que **no** quedó `src/main.jsx`.

## Deploy
1) Sube este proyecto al repo `amante/BeatBetano` (mismo case).  
2) Settings → Pages → Source: **GitHub Actions**.  
3) Push a `main`.

## Verificación
- En el job de Actions verás los logs de “Diagnostics” con el `head` de `dist/index.html` y la búsqueda por `src/main.jsx` (no debe aparecer).
- En producción, **Ver código fuente** debe mostrar `<script type="module" src="/BeatBetano/assets/...js">`.

## Dev
```bash
npm install
npm run dev
```