# Migração: Gemini API → OpenRouter

## Data: 23/02/2026

## Resumo
Todas as páginas que utilizavam a API do Google Gemini diretamente foram migradas para usar o OpenRouter, centralizando a configuração de API e permitindo o uso de múltiplos modelos.

## Arquivos Modificados

### 1. pages/auditor.html
- **Função alterada:** `callGemini()`
- **Mudanças:**
  - Endpoint: `generativelanguage.googleapis.com` → `openrouter.ai/api/v1/chat/completions`
  - Formato de requisição: Gemini format → OpenAI format
  - Suporte a imagens via `image_url` com data URL
  - Autenticação via header `Authorization: Bearer`
  - LocalStorage key: `auditor-gemini-key` → `auditor-openrouter-key`

### 2. pages/gerador-empenho.html
- **Função alterada:** `generateEmpenhoText()`
- **Mudanças:**
  - Endpoint: `generativelanguage.googleapis.com` → `openrouter.ai/api/v1/chat/completions`
  - Formato de requisição: Gemini format → OpenAI format
  - Suporte a imagens via `image_url` com data URL
  - LocalStorage key: `gemini_api_key` → `openrouter_api_key`
  - Variável renomeada: `geminiApiKey` → `openrouterApiKey`

### 3. pages/tarifas-bancarias.html
- **Função alterada:** `summarizeBankFees()`
- **Mudanças:**
  - Endpoint: `generativelanguage.googleapis.com` → `openrouter.ai/api/v1/chat/completions`
  - Formato de requisição: Gemini format → OpenAI format
  - LocalStorage key: `gemini_api_key` → `openrouter_api_key`
  - Variável renomeada: `geminiApiKey` → `openrouterApiKey`
  - Response format: `json_object` para garantir JSON válido

## Mudanças Técnicas Detalhadas

### Formato de Requisição

**Antes (Gemini):**
```javascript
{
  system_instruction: { parts: [{ text: SYSTEM_PROMPT }] },
  contents: [{
    role: 'user',
    parts: [
      { text: "prompt" },
      { inline_data: { mime_type: mime, data: b64 } }
    ]
  }],
  generationConfig: {
    response_mime_type: 'application/json',
    temperature: 0.2
  }
}
```

**Depois (OpenRouter):**
```javascript
{
  model: 'google/gemini-2.0-flash-exp:free',
  messages: [
    { role: 'system', content: SYSTEM_PROMPT },
    { 
      role: 'user', 
      content: [
        { type: 'text', text: "prompt" },
        { type: 'image_url', image_url: { url: dataUrl } }
      ]
    }
  ],
  temperature: 0.2,
  response_format: { type: 'json_object' }
}
```

### Headers

**Antes:**
```javascript
headers: { 
  'Content-Type': 'application/json' 
}
```

**Depois:**
```javascript
headers: {
  'Content-Type': 'application/json',
  'Authorization': `Bearer ${apiKey}`,
  'HTTP-Referer': window.location.origin,
  'X-Title': 'Prefeitura de Inajá – [Nome da Página]'
}
```

### Parsing de Resposta

**Antes:**
```javascript
const text = data?.candidates?.[0]?.content?.parts?.[0]?.text;
```

**Depois:**
```javascript
const text = data?.choices?.[0]?.message?.content;
```

## Configuração do Modelo

Todas as páginas agora usam o modelo configurado em `localStorage`:
```javascript
const model = localStorage.getItem('api_openrouter_modelo') || 'google/gemini-2.0-flash-exp:free';
```

Isso permite que o usuário escolha qualquer modelo disponível no OpenRouter através da interface de administração.

## Interface do Usuário

### Mudanças nos Labels:
- "Chave API Gemini" → "Chave API OpenRouter"
- "Cole sua API Key do Google AI Studio" → "Cole sua API Key do OpenRouter"
- "aistudio.google.com/apikey" → "openrouter.ai/keys"

### Mudanças nas Mensagens:
- "Configure sua chave API Gemini" → "Configure sua chave API OpenRouter"
- "Resposta vazia da API Gemini" → "Resposta vazia da API"
- "Analisando documento com IA Gemini" → "Analisando documento com IA OpenRouter"

## Compatibilidade

- ✅ Mantém suporte a imagens (PDF, JPG, PNG, WebP)
- ✅ Mantém formato de resposta JSON
- ✅ Mantém temperatura e outros parâmetros
- ✅ Modelo padrão continua sendo Gemini (via OpenRouter)
- ✅ Usuário pode trocar para qualquer modelo do OpenRouter

## Ações Necessárias do Usuário

1. Obter chave API do OpenRouter em: https://openrouter.ai/keys
2. Configurar a chave nas páginas:
   - Auditor de Notas Fiscais
   - Gerador de Empenho
   - Tarifas Bancárias
3. (Opcional) Configurar modelo preferido em ADM → OpenRouter

## Notas

- As chaves antigas do Google Gemini não funcionarão mais
- O modelo padrão `google/gemini-2.0-flash-exp:free` está disponível gratuitamente no OpenRouter
- Todas as páginas agora compartilham a mesma configuração de modelo (se configurado via ADM)
- A migração mantém 100% da funcionalidade anterior
