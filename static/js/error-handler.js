// Error Handler - Tratamento centralizado de erros

class ErrorHandler {
  static handle(error, context = '') {
    const errorInfo = this.parseError(error);
    
    // Log do erro
    this.log(errorInfo, context);
    
    // Retornar mensagem amigável
    return this.getUserMessage(errorInfo);
  }

  static parseError(error) {
    if (typeof error === 'string') {
      return { type: 'generic', message: error };
    }

    const message = error.message || 'Erro desconhecido';

    // Erros de API
    if (message.includes('401') || message.includes('Unauthorized')) {
      return { type: 'auth', message: 'Chave API inválida ou expirada' };
    }
    if (message.includes('429') || message.includes('rate limit')) {
      return { type: 'rate_limit', message: 'Limite de requisições atingido. Aguarde alguns minutos.' };
    }
    if (message.includes('402') || message.includes('credits')) {
      return { type: 'credits', message: 'Créditos insuficientes na conta OpenRouter' };
    }
    if (message.includes('400') || message.includes('Bad Request')) {
      return { type: 'bad_request', message: 'Requisição inválida. Verifique o modelo selecionado.' };
    }
    if (message.includes('500') || message.includes('503')) {
      return { type: 'server', message: 'Servidor temporariamente indisponível. Tente novamente.' };
    }

    // Erros de rede
    if (message.includes('Failed to fetch') || message.includes('NetworkError')) {
      return { type: 'network', message: 'Erro de conexão. Verifique sua internet.' };
    }

    // Erros de OCR
    if (message.includes('OCR') || message.includes('extrair texto')) {
      return { type: 'ocr', message: 'Não foi possível ler o documento. Tente com melhor qualidade.' };
    }

    // Erro genérico
    return { type: 'generic', message };
  }

  static getUserMessage(errorInfo) {
    const suggestions = {
      auth: 'Configure uma chave válida na aba ADM.',
      rate_limit: 'Aguarde alguns minutos antes de tentar novamente.',
      credits: 'Verifique seu saldo em openrouter.ai',
      bad_request: 'Selecione outro modelo na aba ADM.',
      server: 'O serviço está temporariamente indisponível.',
      network: 'Verifique sua conexão com a internet.',
      ocr: 'Use um documento com melhor qualidade ou resolução.'
    };

    const suggestion = suggestions[errorInfo.type] || 'Tente novamente ou contate o suporte.';
    return `${errorInfo.message}\n\n💡 ${suggestion}`;
  }

  static log(errorInfo, context) {
    const logEntry = {
      timestamp: new Date().toISOString(),
      type: errorInfo.type,
      message: errorInfo.message,
      context,
      userAgent: navigator.userAgent
    };

    // Salvar no localStorage (últimos 10 erros)
    const logs = JSON.parse(localStorage.getItem('error_logs') || '[]');
    logs.unshift(logEntry);
    localStorage.setItem('error_logs', JSON.stringify(logs.slice(0, 10)));

    // Console para debug
    console.error('[ErrorHandler]', logEntry);
  }

  static getLogs() {
    return JSON.parse(localStorage.getItem('error_logs') || '[]');
  }

  static clearLogs() {
    localStorage.removeItem('error_logs');
  }
}

window.ErrorHandler = ErrorHandler;
