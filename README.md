# BeatBetano (React + Vite) v1.1.0

Deploy en **GitHub Pages** como project site: **https://amante.github.io/beatbetano/**

## Pasos
1. Crea el repo **beatbetano** en tu cuenta `amante`.
2. Sube todo este proyecto (incluida `.github/workflows/pages.yml`).
3. En local:
   ```bash
   npm i
   npm run build
   git init
   git add .
   git commit -m "BeatBetano React v1.1.0"
   git branch -M main
   git remote add origin https://github.com/amante/beatbetano.git
   git push -u origin main
   ```
4. GitHub Actions compila y publica en Pages.
