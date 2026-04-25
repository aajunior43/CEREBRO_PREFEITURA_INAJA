Use este arquivo para propor reorganizações baseadas no tipo de projeto detectado.

---

## Como detectar o tipo de projeto

| Indicador encontrado | Tipo provável |
|---|---|
| `package.json` + `react` nas deps | React / Next.js |
| `package.json` + `express` / `fastify` | Node.js API |
| `requirements.txt` / `pyproject.toml` | Python |
| `package.json` + múltiplos `workspaces` | Monorepo JS |
| `Cargo.toml` | Rust |
| Vários `package.json` em subpastas | Monorepo genérico |
| Nenhum dos acima | Projeto genérico |

---

## 1. React / Next.js

```
projeto/
├── README.md
├── package.json
├── .env.example
├── .gitignore
├── next.config.js (ou vite.config.ts)
│
├── public/              # Estáticos públicos
│
├── src/
│   ├── app/             # (Next 13+) ou pages/
│   ├── components/      # Componentes reutilizáveis
│   │   └── ui/          # Componentes genéricos (botões, inputs)
│   ├── hooks/           # Custom hooks
│   ├── lib/             # Utilitários e helpers
│   ├── services/        # Chamadas de API / integrações externas
│   ├── store/           # Estado global (Redux, Zustand, etc.)
│   ├── styles/          # CSS global
│   └── types/           # TypeScript types/interfaces
│
├── docs/                # Documentação técnica (máximo 3-5 MDs)
│   ├── architecture.md
│   └── setup.md
│
└── archive/             # Código antigo, não deletar ainda
```

**MDs que pertencem aqui:** `README.md` raiz, arquivos dentro de `docs/`.
**MDs que NÃO pertencem:** qualquer `.md` dentro de `src/`, `components/`, `hooks/`.

---

## 2. Node.js API (Express / Fastify / NestJS)

```
projeto/
├── README.md
├── package.json
├── .env.example
├── .gitignore
│
├── src/
│   ├── controllers/     # Handlers de rotas
│   ├── services/        # Lógica de negócio
│   ├── repositories/    # Acesso a dados
│   ├── models/          # Modelos / entidades
│   ├── middlewares/
│   ├── routes/
│   ├── utils/
│   ├── config/          # Configurações centralizadas
│   └── index.ts         # Entry point
│
├── tests/
│   ├── unit/
│   └── integration/
│
├── docs/
│   ├── api.md           # Documentação de endpoints
│   └── setup.md
│
└── archive/
```

---

## 3. Python (scripts / FastAPI / Django)

```
projeto/
├── README.md
├── requirements.txt (ou pyproject.toml)
├── .env.example
├── .gitignore
│
├── src/                 # (ou nome do pacote principal)
│   ├── __init__.py
│   ├── main.py
│   ├── api/             # Rotas (FastAPI/Django)
│   ├── models/
│   ├── services/
│   ├── utils/
│   └── config.py
│
├── tests/
├── scripts/             # Scripts utilitários (migrations, seeds)
│
├── docs/
│   └── setup.md
│
└── archive/
```

---

## 4. Monorepo (Turborepo / Nx / Yarn Workspaces)

```
monorepo/
├── README.md
├── package.json         # Root workspace
├── turbo.json           # (se Turborepo)
├── .gitignore
│
├── apps/
│   ├── web/             # App frontend
│   └── api/             # App backend
│
├── packages/
│   ├── ui/              # Componentes compartilhados
│   ├── utils/           # Utilitários compartilhados
│   └── types/           # Types compartilhados
│
├── docs/                # Documentação do monorepo
│   ├── architecture.md
│   └── contributing.md
│
├── scripts/             # Scripts de build/deploy globais
└── archive/
```

**Atenção em monorepos:** cada `app/` e `package/` pode ter seu próprio `README.md`.
MDs além disso (dentro de `src/`, `components/`, etc.) são candidatos à remoção.

---

## 5. Projeto Genérico / Misto

Quando não há padrão claro, use esta estrutura mínima:

```
projeto/
├── README.md            # Único ponto de entrada da documentação
├── .gitignore
│
├── src/                 # Todo código-fonte aqui
│
├── docs/                # Máximo 5 MDs com propósito claro
│
├── config/              # Arquivos de configuração
│
├── scripts/             # Scripts auxiliares
│
└── archive/             # Tudo que não se sabe se pode deletar
```

---

## Regras universais para MDs

### Onde MDs são bem-vindos
- `README.md` na raiz (obrigatório)
- `README.md` em `packages/` ou `apps/` de monorepos
- Arquivos dentro de `docs/`
- `CONTRIBUTING.md`, `CHANGELOG.md`, `LICENSE.md` na raiz

### Onde MDs geralmente NÃO devem estar
- Dentro de `src/`, `components/`, `hooks/`, `utils/`
- Arquivos como `notas.md`, `rascunho.md`, `temp.md`, `test.md` em qualquer lugar
- Múltiplos MDs com conteúdo sobreposto (`api.md` + `api-docs.md` + `endpoints.md`)
- `README copy.md`, `README (1).md`, `README-old.md`

### Consolidação antes de deletar
Se dois MDs têm conteúdo útil complementar, mescle em um único arquivo antes de deletar o redundante. Nunca jogue fora informação sem verificar se ela existe em outro lugar.