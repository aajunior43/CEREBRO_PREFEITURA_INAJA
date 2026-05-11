// Usage Logger - Rastreamento de uso das ferramentas

class UsageLogger {
  static log(action, details = {}) {
    const entry = {
      timestamp: new Date().toISOString(),
      action,
      details,
      page: window.location.pathname
    };

    // Adicionar ao log
    const logs = this.getLogs();
    logs.push(entry);

    // Manter apenas últimos 100 registros
    if (logs.length > 100) {
      logs.shift();
    }

    localStorage.setItem('usage_logs', JSON.stringify(logs));
  }

  static getLogs() {
    return JSON.parse(localStorage.getItem('usage_logs') || '[]');
  }

  static getStats() {
    const logs = this.getLogs();
    const stats = {
      total: logs.length,
      byAction: {},
      byPage: {},
      last24h: 0
    };

    const now = Date.now();
    const day = 24 * 60 * 60 * 1000;

    logs.forEach(log => {
      // Por ação
      stats.byAction[log.action] = (stats.byAction[log.action] || 0) + 1;
      
      // Por página
      stats.byPage[log.page] = (stats.byPage[log.page] || 0) + 1;
      
      // Últimas 24h
      if (now - new Date(log.timestamp).getTime() < day) {
        stats.last24h++;
      }
    });

    return stats;
  }

  static clear() {
    localStorage.removeItem('usage_logs');
  }

  // Atalhos para ações comuns
  static logAIRequest(tool, model, success) {
    this.log('ai_request', { tool, model, success });
  }

  static logFileUpload(tool, fileType, fileSize) {
    this.log('file_upload', { tool, fileType, fileSize });
  }

  static logPageView(page) {
    this.log('page_view', { page });
  }
}

window.UsageLogger = UsageLogger;

// Log automático de visualizações de página
UsageLogger.logPageView(window.location.pathname);
