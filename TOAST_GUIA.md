# Toast Notifications — Guia de Uso

## Visão Geral

Sistema de notificações visuais (toast) integrado com interceptação global de erros HTTP.

### Características

✅ **Design consistente** — Flat design com suporte a dark mode  
✅ **Animações suaves** — Slide in/out com progress bar  
✅ **Auto-dismiss** — Fecha automaticamente após 5 segundos  
✅ **Interceptor HTTP** — Captura erros 401, 429, 500 automaticamente  
✅ **Acessível** — ARIA labels e roles  
✅ **Responsivo** — Adapta-se a mobile  

---

## Uso Básico

### Importar

```html
<!-- No <head> -->
<link rel="stylesheet" href="/static/css/toast.css" />

<!-- Antes de outros scripts JS -->
<script src="/static/js/toast.js" defer></script>
```

### Mostrar Notificações

```javascript
// Success
Toast.success('Salvo!', 'Dados atualizados com sucesso.')

// Error
Toast.error('Erro', 'Não foi possível conectar ao servidor.')

// Warning
Toast.warning('Atenção', 'Sessão expirando em 5 minutos.')

// Info
Toast.info('Info', 'Backup concluído.')
```

### Opções

```javascript
// Duração customizada (em ms)
Toast.success('Salvo!', 'Dados atualizados.', { duration: 3000 })

// Sem auto-dismiss
Toast.info('Processando...', 'Aguarde.', { duration: 0 })

// Título opcional
Toast.success('', 'Operação concluída.')
```

---

## Erros HTTP Automáticos

### Interceptor Global

O toast intercepta automaticamente erros HTTP de **todas** as requisições `fetch()`:

| Status | Título | Mensagem |
|--------|--------|----------|
| **400** | Requisição Inválida | Verifique os dados enviados |
| **401** | Não Autorizado | Sessão expirada ou credenciais inválidas |
| **403** | Acesso Negado | Sem permissão para este recurso |
| **404** | Não Encontrado | Recurso não encontrado |
| **409** | Conflito | Já existe registro com estes dados |
| **422** | Dados Inválidos | Verifique os campos |
| **429** | Muitas Requisições | Aguarde antes de tentar |
| **500** | Erro do Servidor | Erro interno, tente novamente |
| **502** | Serviço Indisponível | Serviço externo indisponível |
| **503** | Serviço Indisponível | Sistema em manutenção |

### Exemplo

```javascript
// Erro 401 será interceptado automaticamente
const response = await fetch('/api/credores')
// Toast aparece: "Não Autorizado — Sessão expirada..."

// Erro 429 será interceptado automaticamente
const response = await fetch('/api/ia/chat', {
  method: 'POST',
  body: JSON.stringify({ message: 'test' })
})
// Toast aparece: "Muitas Requisições — Aguarde..."
```

---

## Uso com ErrorHandler Existente

O `ErrorHandler` foi integrado com toasts:

```javascript
// Antes: Apenas retornava mensagem
try {
  const data = await callAPI()
} catch (error) {
  const msg = ErrorHandler.handle(error, 'Gerador')
  alert(msg)
}

// Agora: Mostra toast E retorna mensagem
try {
  const data = await callAPI()
} catch (error) {
  const msg = ErrorHandler.handle(error, 'Gerador')
  // Toast já foi mostrado automaticamente!
  console.log(msg)
}
```

---

## Métodos Avançados

### Interceptação Manual de Response

```javascript
const response = await fetch('/api/credores', { method: 'POST', body })

// Verificar e mostrar erro se necessário
await Toast.handleFetchResponse(response, { context: 'Criar credor' })

if (!response.ok) {
  // Tratamento customizado
  return
}

// Continuar com resposta OK
const data = await response.json()
```

### Parse de Erro

```javascript
const errorInfo = Toast.parseHttpError({
  status: 429,
  message: 'Rate limit exceeded'
})

console.log(errorInfo)
// {
//   type: 'rate-limit',
//   title: 'Muitas Requisições',
//   message: 'Aguarde alguns instantes...',
//   duration: 6000
// }
```

### Limpar Todos os Toasts

```javascript
Toast.clearAll()
```

---

## Customização CSS

### Cores

Os toasts usam variáveis CSS do tema:

```css
/* Light mode */
:root {
  --green: #3aaa6e;
  --green-bg: #d4f5e3;
  --red: #c74a4a;
  --red-bg: #fdd8d8;
  --orange: #d97c3a;
  --orange-bg: #fde8d4;
  --blue: #4f80c8;
  --blue-light: #dde9ff;
}

/* Dark mode */
[data-theme="dark"] {
  --green: #4ade80;
  --green-bg: #064e3b;
  --red: #f87171;
  --red-bg: #7f1d1d;
  /* etc. */
}
```

### Sobrescrever Estilos

```css
/* Toast custom */
.toast-minha-classe {
  border-left-color: purple;
}

.toast-minha-classe .toast-icon {
  color: purple;
  background: #f3e8ff;
}
```

---

## Exemplos Práticos

### Formulário de Login

```javascript
async function login(username, password) {
  try {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password })
    })

    // Toast automático para 401, 500, etc.
    if (!response.ok) return

    const data = await response.json()
    Toast.success('Login', `Bem-vindo, ${data.name}!`)
    
  } catch (error) {
    Toast.error('Erro de Conexão', 'Verifique sua internet.')
  }
}
```

### Upload de Arquivo

```javascript
async function uploadFile(file) {
  const fd = new FormData()
  fd.append('file', file)

  try {
    const response = await fetch('/api/documentos', {
      method: 'POST',
      body: fd
    })

    await Toast.handleFetchResponse(response, { context: 'Upload' })
    
    if (!response.ok) return
    
    Toast.success('Upload', `${file.name} enviado com sucesso.`)
    
  } catch (error) {
    Toast.error('Upload Falhou', error.message)
  }
}
```

### Operação em Lote

```javascript
async function empenharLote(credores) {
  Toast.info('Processando', `Empenhando ${credores.length} credores...`, { duration: 0 })
  
  try {
    const response = await fetch('/api/empenhos/lote', {
      method: 'POST',
      body: JSON.stringify({ itens: credores })
    })

    Toast.clearAll() // Limpar "Processando"

    await Toast.handleFetchResponse(response)
    
    if (!response.ok) return
    
    const data = await response.json()
    Toast.success('Concluído', `${data.resultados.length} empenhos processados.`)
    
  } catch (error) {
    Toast.clearAll()
    Toast.error('Erro', 'Falha ao processar empenhos.')
  }
}
```

---

## Estrutura HTML do Toast

```html
<div id="toast-container">
  <div class="toast toast-success" role="alert" aria-live="assertive">
    <div class="toast-icon">✓</div>
    <div class="toast-content">
      <div class="toast-title">Salvo!</div>
      <div class="toast-message">Dados atualizados com sucesso.</div>
    </div>
    <button class="toast-close" aria-label="Fechar">×</button>
    <div class="toast-progress"></div>
  </div>
</div>
```

---

## Configurações

```javascript
// Duração padrão (5 segundos)
Toast.defaultDuration = 5000

// Máximo de toasts simultâneos
Toast.maxToasts = 5
```

---

## Compatibilidade

| Navegador | Versão |
|-----------|--------|
| Chrome | 60+ |
| Firefox | 55+ |
| Safari | 12+ |
| Edge | 79+ |
| Mobile Safari | iOS 12+ |
| Chrome Android | 60+ |

---

## Troubleshooting

### Toast Não Aparece

1. Verificar se CSS foi carregado:
   ```javascript
   console.log(document.getElementById('toast-container'))
   // Deve retornar o elemento
   ```

2. Verificar se JS foi carregado:
   ```javascript
   console.log(window.Toast)
   // Deve retornar o objeto Toast
   ```

### Múltiplos Toasts Iguais

O sistema limita a 5 toasts simultâneos. O mais antigo é removido automaticamente.

### Interceptor Não Funciona

O interceptor só captura respostas com status 401, 403, 429, 500, 502, 503. Outros status passam normalmente.

---

## Referências

- `static/css/toast.css` — Estilos
- `static/js/toast.js` — Lógica principal
- `static/js/error-handler.js` — Integração com ErrorHandler
