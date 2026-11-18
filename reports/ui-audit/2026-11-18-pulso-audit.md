# Auditoría de interfaz PULSO — 18 de noviembre de 2026

## Alcance

Revisión estática de la estructura HTML, estilos y lógica de organización de paneles en el frontend de PULSO, con criterios de accesibilidad WCAG 2.2 y pautas generales de usabilidad. Esta revisión no equivale a una evaluación formal de conformidad WCAG ni incluye pruebas con lector de pantalla u otras tecnologías de asistencia.

## Hallazgos

### 1. Jerarquía de la página

La lógica de `frontend/pulso-ui.js` reubica paneles en “Más análisis y herramientas”, dejando fuera solo algunos elementos principales. La ejecución manual, los resultados NBA y secciones del modelo NHL pueden quedar agrupados lejos del calendario y del resultado más reciente. Esto contradice el flujo principal que necesita el usuario: calendario → ejecución manual → resultado.

**Prioridad: alta.** Definir una jerarquía común por deporte y mantener las acciones y resultados principales visibles y en orden. El contenido secundario debe usar acordeones con títulos descriptivos.

### 2. Contraste y legibilidad

La interfaz usa una paleta casi exclusivamente oscura. La mayoría de los textos principales son claros; sin embargo, el texto secundario `#819bab` sobre el gradiente claro de paneles llega aproximadamente a una relación de contraste de 4.25:1, por debajo del mínimo WCAG AA de 4.5:1 para texto normal. Se utiliza en metadatos como `.daily-source` y textos secundarios de acordeones.

También aparecen metadatos y estados de jugadores con tamaños aproximados de 9–11 px. Aunque el tamaño tipográfico por sí solo no determina conformidad, dificulta lectura rápida, especialmente en móvil.

**Prioridad: alta.** Aclarar la paleta y subir el contraste de textos secundarios. Aumentar tipografía auxiliar, espaciamiento entre líneas y separación entre iconos y texto. Conservar color de estado más una etiqueta textual, sin comunicar significado solo mediante color.

### 3. Iconografía

Hay una combinación de emoji, caracteres, SVG y logos de equipos. El estilo cambia entre módulos y algunos símbolos pueden anunciarse de forma poco útil a tecnologías de asistencia.

**Prioridad: media.** Usar una familia consistente de iconos SVG; añadir una etiqueta visible a los iconos funcionales; marcar los decorativos como ocultos a lectores de pantalla. Mantener los logos de equipos con texto alternativo que identifique al equipo.

### 4. Estructura semántica

La página base de NBA no expone un encabezado principal `h1`; el encabezado se inserta dinámicamente en el flujo NHL. Conviene que cada deporte tenga un título principal persistente y una jerarquía de encabezados clara.

**Prioridad: media.** Asegurar un `h1` por vista y nombres accesibles para botones, fechas, acordeones y resultados.

### 5. Reflujo, teclado y objetivos de interacción

No se midió manualmente cada control ni se probó navegación completa por teclado. La revisión del código debe complementarse con una comprobación responsive a 320 CSS px y zoom de 200–400%, foco visible, orden de tabulación y objetivos táctiles de al menos 24×24 CSS px cuando aplique WCAG 2.2 AA.

**Prioridad: alta para validación.** Incluir una pasada manual en escritorio y móvil después de cada etapa del rediseño.

## Secuencia sugerida

1. **Ordenar el flujo principal:** calendario, ejecución manual y resultado reciente; comprobarlo en NBA y NHL.
2. **Mejorar lectura y contraste:** ajustar color de metadatos, tamaños, interlineado y espacios.
3. **Unificar iconos y etiquetas:** aplicar el mismo lenguaje visual y accesible a ambos deportes.
4. **Validar interacción y reflujo:** teclado, foco, zoom, móvil, contraste y objetivos táctiles.
5. **Cerrar con revisión visual y accesible:** confirmar que los datos importantes siguen siendo localizables y que los detalles quedan bajo acordeones claros.

## Referencias

- W3C WAI en español: https://www.w3.org/WAI/standards-guidelines/es
- Estándares W3C: https://www.w3.org/standards/
- WCAG 2.2: https://www.w3.org/TR/WCAG22/
- Comprender contraste mínimo: https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html
- Comprender tamaño mínimo de objetivo: https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
- Pautas de usabilidad citadas para la revisión: https://www.tooltyp.com/10-leyes-ux-pautas-diseno-web-la-hora-mejorar-la-experiencia-usuario/

## Nota sobre colores

La estimación de contraste se calculó contra el extremo más claro del gradiente de paneles identificado en los estilos revisados. Debe repetirse sobre capturas renderizadas y estados reales antes de modificar la paleta.
