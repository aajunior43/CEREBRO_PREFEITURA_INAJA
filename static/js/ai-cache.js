// AI Response Cache Manager
// Armazena respostas da IA para evitar chamadas duplicadas

class AICache {
  constructor(maxSize = 50, ttl = 3600000) { // 1 hora
    this.cache = new Map();
    this.maxSize = maxSize;
    this.ttl = ttl;
  }

  generateKey(prompt, model) {
    return `${model}:${this.hashString(prompt)}`;
  }

  hashString(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash;
    }
    return hash.toString(36);
  }

  get(prompt, model) {
    const key = this.generateKey(prompt, model);
    const cached = this.cache.get(key);
    
    if (!cached) return null;
    
    // Verificar expiração
    if (Date.now() - cached.timestamp > this.ttl) {
      this.cache.delete(key);
      return null;
    }
    
    return cached.response;
  }

  set(prompt, model, response) {
    const key = this.generateKey(prompt, model);
    
    // Limpar cache se atingir tamanho máximo
    if (this.cache.size >= this.maxSize) {
      const firstKey = this.cache.keys().next().value;
      this.cache.delete(firstKey);
    }
    
    this.cache.set(key, {
      response,
      timestamp: Date.now()
    });
  }

  clear() {
    this.cache.clear();
  }

  getStats() {
    return {
      size: this.cache.size,
      maxSize: this.maxSize,
      ttl: this.ttl
    };
  }
}

// Instância global
window.aiCache = new AICache();
