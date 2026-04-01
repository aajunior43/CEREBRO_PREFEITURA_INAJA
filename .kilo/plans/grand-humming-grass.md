# Plano: Melhorar Responsividade Mobile

## Contexto
O sistema de Empenhos Mensais (Prefeitura de Inajá) possui 22+ páginas HTML. A responsividade mobile atual é inconsistente: algumas páginas têm media queries bem definidas, outras não têm nenhuma. O CSS global (`index.css`) tem breakpoints em 860px, 900px e 600px mas faltam ajustes em vários componentes.

## Problemas Identificados

### 1. Páginas SEM nenhuma media query mobile
- **`rpa.html`** — grid de formulário `1fr 1fr` e `1fr 1fr 1fr` não quebra; lista com colunas fixas (60px, 1fr, 140px, 120px, 120px, 100px) não se adapta
- **`cnpj.html`** — sem media queries; `cnpj-input-row` com `display:flex` não empilha; `info-grid` pode cortar
- **`visualizador.html`** — sidebar fixa de 300px, tabela com colunas fixas ilegível em <768px, tem apenas `@media print`

### 2. Navegação de mês escondida em mobile
- O seletor de mês (`month-nav`) é escondido com `display:none` em 600px sem alternativa — o usuário perde acesso à navegação de mês no celular

### 3. Toolbar da página principal
- Em 600px, botões de ação ficam 50% width — com muitos botões, alguns ficam apertados

### 4. Inconsistência de breakpoints
- Cada página define seus próprios breakpoints (500px a 1200px), falta padronização

### 5. Touch targets pequenos
- Alguns botões e controles podem ter menos de 44x44px (WCAG 2.5.5)

---

## Plano de Implementação

### Etapa 1: CSS Global — Breakpoints e month-nav
**Arquivo:** `static/css/index.css`

- Melhorar `month-nav` em mobile: em vez de `display:none`, usar formato compacto (ex: "Fev 2026") com setas
- Ajustar `toolbar-actions` para scroll horizontal ou grid 3-col quando couber
- Adicionar `padding-bottom` com `env(safe-area-inset-bottom)` no bottom-nav

### Etapa 2: Página RPA (`pages/rpa.html`)
- Adicionar `@media (max-width: 600px)`:
  - `.form-grid-2, .form-grid-3` → `grid-template-columns: 1fr`
  - `.rpa-list-item` → layout de card vertical
  - `.rpa-list-header` → esconder
  - `.faixa-row` → `grid-template-columns: 1fr 1fr`

### Etapa 3: Página CNPJ (`pages/cnpj.html`)
- Adicionar `@media (max-width: 600px)`:
  - `.cnpj-input-row` → `flex-direction: column`
  - `.btn-cnpj` → `width: 100%`
  - `.info-grid` → `grid-template-columns: 1fr`

### Etapa 4: Página Visualizador (`pages/visualizador.html`)
- `@media (max-width: 1024px)`: sidebar como overlay toggle, tabela scroll horizontal
- `@media (max-width: 600px)`: layout cards em vez de tabela

### Etapa 5: Renomeador (`pages/renomear.html`)
- Verificar e adicionar media queries se necessário

---

## Arquivos a modificar
1. `static/css/index.css` — month-nav compacto, toolbar, bottom-nav safe-area
2. `pages/rpa.html` — media queries
3. `pages/cnpj.html` — media queries
4. `pages/visualizador.html` — media queries + layout alternativo
5. `pages/renomear.html` — verificar/adicionar media queries
6. `index.html` — month-nav

## Verificação
- Testar em: 375px (iPhone SE), 390px (iPhone 14), 768px (iPad), 1024px (iPad landscape)
- Verificar navegação de mês funciona em mobile
- Verificar touch targets ≥ 44px
