// Error Handler - Tratamento centralizado de erros
// Integrado com Toast Notifications

class ErrorHandler {
  static handle(error, context = '') {
    const errorInfo = this.parseError(error);

    // Log do erro
    this.log(errorInfo, context);

    // Mostrar toast com erro
    if (window.Toast) {
      Toast.handleHttpError({
        status: errorInfo.status || 0,
        message: errorInfo.message
      }, context);
    }

    // Retornar mensagem amigável
    return this.getUserMessage(errorInfo);
  }

  static parseError(error) {
    if (typeof error === 'string') {
      return { type: 'generic', message: error, status: 0 };
    }

    const status = error.status || error.response?.status || 0;
    const message = error.message || error.error?.message || 'Erro desconhecido';

    // Erros de API
    if (status === 401 || message.includes('401') || message.includes('Unauthorized')) {
      return { type: 'auth', message: 'Chave API inválida ou expirada', status: 401 };
    }
    if (status === 429 || message.includes('429') || message.includes('rate limit')) {
      return { type: 'rate_limit', message: 'Limite de requisições atingido. Aguarde alguns minutos.', status: 429 };
    }
    if (status === 402 || message.includes('402') || message.includes('credits')) {
      return { type: 'credits', message: 'Créditos insuficientes na conta OpenRouter', status: 402 };
    }
    if (status === 400 || message.includes('400') || message.includes('Bad Request')) {
      return { type: 'bad_request', message: 'Requisição inválida. Verifique o modelo selecionado.', status: 400 };
    }
    if (status === 500 || status === 503 || message.includes('500') || message.includes('503')) {
      return { type: 'server', message: 'Servidor temporariamente indisponível. Tente novamente.', status: status || 500 };
    }

    // Erros de rede
    if (message.includes('Failed to fetch') || message.includes('NetworkError')) {
      return { type: 'network', message: 'Erro de conexão. Verifique sua internet.', status: 0 };
    }

    // Erros de OCR
    if (message.includes('OCR') || message.includes('extrair texto')) {
      return { type: 'ocr', message: 'Não foi possível ler o documento. Tente com melhor qualidade.', status: 0 };
    }

    // Erro genérico
    return { type: 'generic', message, status };
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
