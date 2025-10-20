# BeatBetano (React + Vite) v1.0.0

Gestor de apuestas deportivas con **React + Vite + Tailwind**, listo para deploy en **GitHub Pages** como **project site** en el repo `amante.beatbetano`.

## 🚀 Características
- Bet Builder (múltiples legs) con cálculo de **parlay** y retorno
- Gestión de apuestas (OPEN/WON/LOST/VOID)
- **Banca**: depósitos/retiros y movimientos automáticos al liquidar
- Exportar/Importar **JSON / CSV / XLSX** (usa SheetJS)
- Persistencia en `localStorage`
- Configurable en **CLP / USD / EUR** y **cuotas American/Decimal/Fraccional**
- UI con Tailwind + iconos de `lucide-react`

## 🛠️ Dev
```bash
npm i
npm run dev
```

## 🧱 Build
```bash
npm run build
# genera dist/ y copia dist/index.html -> dist/404.html (fallback GH Pages)
```

## 🌐 Deploy en GitHub Pages
1. Crea el repositorio **amante.beatbetano** en tu cuenta.
2. Sube **todo** este proyecto (incluyendo `.github/workflows/pages.yml`).
3. Push a la rama **main**. El workflow compilará y publicará en **Pages**.
4. URL final: `https://amante.github.io/amante.beatbetano/`

> Nota: En `vite.config.js` el `base` ya está en `/amante.beatbetano/` (necesario para rutas y assets en un project site).
