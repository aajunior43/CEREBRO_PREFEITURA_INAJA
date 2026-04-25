Guia detalhado para classificar MDs como "manter", "consolidar" ou "remover".

---

## Fluxo de decisão

```
Para cada .md encontrado:

1. É README.md na raiz ou em pasta de pacote?
   → SIM: MANTER sempre

2. Está dentro de docs/?
   → SIM: Avaliar conteúdo (ir para passo 4)

3. Está dentro de src/, components/, hooks/, utils/ ou similar?
   → SIM: Candidato forte à remoção (verificar se tem conteúdo útil)

4. Tem menos de 5 linhas úteis?
   → SIM: REMOVER (ou absorver em outro MD)

5. Seu conteúdo já existe em outro MD?
   → SIM: REMOVER o duplicado, manter o mais completo

6. O nome sugere temporariedade?
   → SIM: REMOVER (ver lista de nomes suspeitos abaixo)

7. É referenciado por algum outro arquivo?
   → NÃO: Forte candidato à remoção

→ Se chegou aqui sem remoção: MANTER em docs/
```

---

## Nomes que indicam MD desnecessário

### Remoção automática (confirmar com usuário)
- `notas.md`, `nota.md`
- `rascunho.md`, `rascunho-*.md`
- `temp.md`, `tmp.md`
- `untitled.md`
- `test.md`, `teste.md`
- `TODO.md` (se estiver vazio ou com itens antigos)
- `lembrete.md`
- `old-*.md`, `*-old.md`, `*-backup.md`
- `README copy.md`, `README (1).md`, `readme2.md`
- `wip.md` (work in progress abandonado)

### Investigar antes de decidir
- `ideas.md` — pode ter valor, verificar data e conteúdo
- `notes.md` — idem
- `todo.md` — verificar se os itens ainda são relevantes
- `*.draft.md` — pode estar em uso ativo

---

## Critérios de conteúdo

### MD com menos de 5 linhas úteis
"Linhas úteis" = linhas que não são:
- Linha em branco
- Só um título (`# Título`)
- Comentário vazio (`<!-- TODO -->`)
- Placeholder (`...`, `TBD`, `em breve`)

Se após remover essas linhas sobram menos de 5 → candidato à remoção.

### MD duplicado
Dois MDs são duplicados se:
- Têm o mesmo assunto principal
- Um é subconjunto do outro
- São versões de datas diferentes do mesmo documento

**Ação:** mesclar o conteúdo único do menor no maior, depois deletar o menor.

### MD órfão
Um MD é órfão se nenhum arquivo do projeto o referencia:

```bash
# Verificar se um MD é referenciado
grep -r "nome-do-arquivo.md" . --include="*.md" --include="*.ts" \
  --include="*.js" --include="*.json" --include="*.yaml" \
  -l 2>/dev/null | grep -v node_modules
```

Se não aparecer em nenhum resultado → orphan, candidato à remoção.

---

## Consolidação de MDs

Quando múltiplos MDs cobrem o mesmo tema, consolidar em um único arquivo.

### Exemplo: API docs espalhados
```
ANTES:
├── api.md              (endpoints básicos)
├── api-docs.md         (exemplos de uso)
├── endpoints.md        (lista de rotas)
└── auth-api.md         (endpoints de auth)

DEPOIS:
└── docs/
    └── api.md          (tudo consolidado com seções)
```

### Template de consolidação

```markdown
# API Reference

## Autenticação
(conteúdo de auth-api.md)

## Endpoints
(conteúdo de endpoints.md)

### Exemplos de uso
(conteúdo de api-docs.md)
```

---

## MDs que NUNCA devem ser removidos sem aviso explícito

- `README.md` (qualquer pasta)
- `CHANGELOG.md`
- `CONTRIBUTING.md`
- `LICENSE.md` / `LICENSE`
- `SECURITY.md`
- `CODE_OF_CONDUCT.md`
- Qualquer MD referenciado no README principal
- Qualquer MD com mais de 50 linhas (verificar com usuário antes)

---

## Apresentando resultados ao usuário

Sempre apresente em formato de tabela:

```
TRIAGEM DE ARQUIVOS MARKDOWN
─────────────────────────────────────────────────────
Arquivo                    Linhas  Status      Motivo
─────────────────────────────────────────────────────
README.md                  42      ✅ Manter   Documento principal
docs/api.md                87      ✅ Manter   Documentação ativa
docs/setup.md              31      ✅ Manter   Referenciado no README
notas.md                   3       🗑️ Remover   Nota pessoal vazia
rascunho-api.md            11      🗑️ Remover   Duplica docs/api.md
untitled.md                1       🗑️ Remover   Só título, sem conteúdo
old-readme.md              28      📦 Arquivar  Versão antiga, pode ter valor
temp-ideas.md              15      ❓ Confirmar Conteúdo incerto
─────────────────────────────────────────────────────
Total: 8 MDs → 3 manter, 3 remover, 1 arquivar, 1 confirmar
```