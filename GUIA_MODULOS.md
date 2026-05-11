# Guia de Uso dos Módulos de Otimização

## 1. Cache de Respostas

### Uso Básico
```javascript
// Antes de fazer requisição à API
const cached = window.aiCache.get(prompt, model);
if (cached) {
  return cached; // Usar resposta em cache
}

// Após receber resposta da API
window.aiCache.set(prompt, model, response);
```

### Exemplo Completo
```javascript
async function generateWithCache(prompt) {
  const model = localStorage.getItem('api_openrouter_modelo') || 'meta-llama/llama-3.2-3b-instruct:free';
  
  // Verificar cache
  const cached = window.aiCache.get(prompt, model);
  if (cached) {
    console.log('✅ Resposta do cache');
    return cached;
  }

  // Fazer requisição
  const response = await callAPI(prompt, model);
  
  // Salvar no cache
  window.aiCache.set(prompt, model, response);
  
  return response;
}
```

## 2. Tratamento de Erros

### Uso Básico
```javascript
try {
  const result = await someAPICall();
} catch (error) {
  const userMessage = ErrorHandler.handle(error, 'Gerador de Empenho');
  showError(userMessage);
}
```

### Ver Logs de Erros
```javascript
// No console do navegador
ErrorHandler.getLogs();

// Limpar logs
ErrorHandler.clearLogs();
```

## 3. Logs de Uso

### Registrar Ações
```javascript
// Requisição de IA
UsageLogger.logAIRequest('gerador-empenho', 'llama-3.2', true);

// Upload de arquivo
UsageLogger.logFileUpload('auditor', 'pdf', 1024000);

// Ação customizada
UsageLogger.log('custom_action', { detail1: 'value1' });
```

### Ver Estatísticas
```javascript
// No console do navegador
const stats = UsageLogger.getStats();
console.log(stats);
// {
//   total: 45,
//   byAction: { ai_request: 20, file_upload: 15, ... },
//   byPage: { '/pages/gerador-empenho.html': 10, ... },
//   last24h: 30
// }
```

## 4. OCR Otimizado

### Uso Básico
```javascript
// Com barra de progresso
const text = await OCROptimizer.extractTextOptimized(file, (progress) => {
  console.log(`${progress.current}/${progress.total}`);
  updateProgressBar(progress.current / progress.total * 100);
});
```

### Otimizar Imagem Antes de Processar
```javascript
const optimizedFile = await OCROptimizer.optimizeImage(largeImageFile);
// Imagens > 5MB são redimensionadas automaticamente
```

### Dividir Texto Grande
```javascript
const chunks = OCROptimizer.chunkText(longText, 4000);
// Processa cada chunk separadamente se necessário
```

## Integração Completa

### Exemplo: Gerador de Empenho com Todos os Módulos

```javascript
async function generateEmpenhoOptimized(file) {
  try {
    // 1. Log de upload
    UsageLogger.logFileUpload('gerador-empenho', file.type, file.size);
    
    // 2. OCR otimizado com progresso
    showLoader('Extraindo texto do documento...');
    const text = await OCROptimizer.extractTextOptimized(file, (progress) => {
      updateProgress(progress.current, progress.total);
    });
    
    // 3. Verificar cache
    const model = localStorage.getItem('api_openrouter_modelo');
    const cached = window.aiCache.get(text, model);
    
    if (cached) {
      UsageLogger.log('cache_hit', { tool: 'gerador-empenho' });
      return cached;
    }
    
    // 4. Fazer requisição
    showLoader('Gerando texto de empenho...');
    const response = await callOpenRouter(text, model);
    
    // 5. Salvar no cache
    window.aiCache.set(text, model, response);
    
    // 6. Log de sucesso
    UsageLogger.logAIRequest('gerador-empenho', model, true);
    
    return response;
    
  } catch (error) {
    // 7. Tratamento de erro
    UsageLogger.logAIRequest('gerador-empenho', model, false);
    const userMessage = ErrorHandler.handle(error, 'Gerador de Empenho');
    throw new Error(userMessage);
  }
}
```

## Painel de Administração

### Ver Estatísticas no Console
```javascript
// Cache
console.log('Cache:', window.aiCache.getStats());

// Erros
console.log('Erros:', ErrorHandler.getLogs());

// Uso
console.log('Uso:', UsageLogger.getStats());
```

### Limpar Dados
```javascript
// Limpar cache
window.aiCache.clear();

// Limpar logs de erro
ErrorHandler.clearLogs();

// Limpar logs de uso
UsageLogger.clear();
```

## Benefícios

1. **Cache**: Reduz custos e melhora velocidade
2. **Erros**: Mensagens claras e acionáveis
3. **Logs**: Rastreamento de uso e problemas
4. **OCR**: Processa documentos grandes sem travar

## Notas

- Cache expira em 1 hora (configurável)
- Logs mantêm últimos 100 registros
- OCR limita PDFs a 50 páginas
- Imagens > 5MB são redimensionadas automaticamente

---

## Atualização: OCR para PDFs Escaneados

### Funcionalidades Adicionadas

#### 1. OCR Automático em PDFs Escaneados
O sistema agora detecta automaticamente páginas escaneadas (com pouco texto) e aplica OCR:

```javascript
// Uso automático - detecta se precisa OCR
const text = await OCROptimizer.extractTextOptimized(pdfFile, (progress) => {
  console.log(`${progress.status}: ${progress.current}/${progress.total}`);
});
```

#### 2. Forçar OCR em Todo o PDF
Para PDFs 100% escaneados, use a função específica:

```javascript
// Força OCR em todas as páginas
const text = await OCROptimizer.extractFromPDFWithOCR(pdfFile, (progress) => {
  console.log(`${progress.status}: ${progress.current}/${progress.total}`);
});
```

### Como Funciona

1. **Extração Híbrida** (padrão):
   - Tenta extrair texto nativo primeiro
   - Se página tem < 50 caracteres, aplica OCR
   - Combina texto nativo + OCR conforme necessário

2. **OCR Completo** (forçado):
   - Renderiza cada página como imagem
   - Aplica OCR em todas as páginas
   - Ideal para documentos 100% escaneados

### Exemplo com Progresso Detalhado

```javascript
const text = await OCROptimizer.extractTextOptimized(file, (progress) => {
  // progress.status pode ser:
  // - "Processando página X"
  // - "OCR na página X"
  // - "Reconhecendo texto..."
  
  updateUI(progress.status, progress.current, progress.total);
});
```

### Limitações

- Máximo 50 páginas por PDF
- PDFs muito grandes são truncados automaticamente
- OCR é mais lento que extração de texto nativo
- Qualidade do OCR depende da qualidade da imagem

### Tipos de PDF Suportados

✅ **PDF com texto nativo** - Extração rápida  
✅ **PDF escaneado** - OCR automático  
✅ **PDF misto** - Híbrido (texto + OCR)  
✅ **Imagens** - OCR completo

### Performance

| Tipo | Velocidade | Qualidade |
|------|-----------|-----------|
| Texto nativo | ⚡⚡⚡ Muito rápido | 100% |
| OCR automático | ⚡⚡ Rápido | 95%+ |
| OCR forçado | ⚡ Moderado | 90%+ |

