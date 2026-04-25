# Referência de Componentes React

**Nota:** Este documento serve como referência para integração de componentes React externos no projeto.

---

## Contexto

O projeto principal **CREDORES_FIXOS_MENSAIR** é uma aplicação Flask (Python) com frontend em HTML/CSS/JavaScript vanilla. 

Este documento foi criado para referência futura caso haja necessidade de integrar componentes React.

---

## Componente de Referência: Travel Connect Sign-In

Um componente de login moderno foi analisado como referência visual. Características:

### Tech Stack
- React + TypeScript
- Tailwind CSS
- Framer Motion (animações)
- Lucide React (ícones)
- shadcn/ui (estrutura)

### Funcionalidades
- Card de login com layout split
- Animação de mapa mundial com rotas (Canvas)
- Login com Google
- Toggle de visibilidade de senha
- Efeitos de hover e transição

### Dependências
```bash
npm install lucide-react framer-motion
```

---

## Integração Futura

Se houver necessidade de integrar React no projeto Flask:

### Opção 1: Standalone
- Criar app React separado
- Servir via Flask como static files
- Comunicação via API REST

### Opção 2: Híbrido
- Usar React apenas em páginas específicas
- Manter Flask como backend API
- Integração via fetch/axios

### Opção 3: Manter Vanilla
- Continuar com HTML/CSS/JS atual
- Usar bibliotecas leves (Alpine.js, htmx)
- Manter simplicidade

---

## Assets Visuais

O componente de referência inclui:
- Animação de mapa com pontos (Canvas API)
- Gradientes modernos (bg-gradient-to-br)
- Design dark mode
- Layout responsivo

Para implementação similar em vanilla JS, considerar:
- Canvas API para animações
- CSS custom properties para temas
- CSS Grid/Flexbox para layouts

---

**Criado em:** 21/04/2026  
**Finalidade:** Referência para integração React futura  
**Status:** ⏸️ Em espera (não prioritário)
