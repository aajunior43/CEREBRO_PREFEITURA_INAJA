// OCR Optimizer - Otimizações para documentos grandes

class OCROptimizer {
  static async optimizeImage(file) {
    // Se arquivo for muito grande, redimensionar
    if (file.size > 5 * 1024 * 1024) { // > 5MB
      return await this.resizeImage(file, 2000); // max 2000px
    }
    return file;
  }

  static async resizeImage(file, maxSize) {
    return new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const img = new Image();
        img.onload = () => {
          const canvas = document.createElement('canvas');
          let width = img.width;
          let height = img.height;

          // Calcular novo tamanho mantendo proporção
          if (width > height && width > maxSize) {
            height = (height * maxSize) / width;
            width = maxSize;
          } else if (height > maxSize) {
            width = (width * maxSize) / height;
            height = maxSize;
          }

          canvas.width = width;
          canvas.height = height;

          const ctx = canvas.getContext('2d');
          ctx.drawImage(img, 0, 0, width, height);

          canvas.toBlob((blob) => {
            resolve(new File([blob], file.name, { type: 'image/jpeg' }));
          }, 'image/jpeg', 0.85);
        };
        img.src = e.target.result;
      };
      reader.readAsDataURL(file);
    });
  }

  static async extractTextOptimized(file, progressCallback) {
    const fileType = file.type;

    // PDF
    if (fileType === 'application/pdf') {
      return await this.extractFromPDF(file, progressCallback);
    }

    // Imagem
    if (fileType.startsWith('image/')) {
      const optimized = await this.optimizeImage(file);
      return await this.extractFromImage(optimized, progressCallback);
    }

    throw new Error('Tipo de arquivo não suportado');
  }

  static async extractFromPDF(file, progressCallback) {
    const arrayBuffer = await file.arrayBuffer();
    const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
    
    let fullText = '';
    const totalPages = pdf.numPages;

    for (let i = 1; i <= totalPages; i++) {
      if (progressCallback) {
        progressCallback({ current: i, total: totalPages, status: 'Processando página ' + i });
      }

      const page = await pdf.getPage(i);
      
      // Tentar extrair texto nativo primeiro
      const textContent = await page.getTextContent();
      const pageText = textContent.items.map(item => item.str).join(' ');
      
      // Se página tem pouco texto, pode ser PDF escaneado - fazer OCR
      if (pageText.trim().length < 50) {
        if (progressCallback) {
          progressCallback({ current: i, total: totalPages, status: 'OCR na página ' + i });
        }
        
        const ocrText = await this.ocrPDFPage(page);
        fullText += ocrText + '\n';
      } else {
        fullText += pageText + '\n';
      }

      // Limitar a 50 páginas para evitar timeout
      if (i >= 50) {
        fullText += '\n[Documento truncado - primeiras 50 páginas]';
        break;
      }
    }

    return fullText;
  }

  static async ocrPDFPage(page) {
    try {
      // Renderizar página como imagem
      const viewport = page.getViewport({ scale: 2.0 });
      const canvas = document.createElement('canvas');
      const context = canvas.getContext('2d');
      canvas.width = viewport.width;
      canvas.height = viewport.height;

      await page.render({
        canvasContext: context,
        viewport: viewport
      }).promise;

      // Converter canvas para blob
      const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.95));
      
      // Fazer OCR
      const result = await Tesseract.recognize(blob, 'por');
      return result.data.text;
    } catch (error) {
      console.warn('OCR falhou na página:', error);
      return '';
    }
  }

  static async extractFromImage(file, progressCallback) {
    if (progressCallback) {
      progressCallback({ current: 0, total: 100, status: 'Iniciando OCR...' });
    }

    const result = await Tesseract.recognize(file, 'por', {
      logger: (m) => {
        if (progressCallback && m.status === 'recognizing text') {
          progressCallback({ 
            current: Math.round(m.progress * 100), 
            total: 100,
            status: 'Reconhecendo texto...'
          });
        }
      }
    });

    return result.data.text;
  }

  // Forçar OCR em todo o PDF (para PDFs 100% escaneados)
  static async extractFromPDFWithOCR(file, progressCallback) {
    const arrayBuffer = await file.arrayBuffer();
    const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
    
    let fullText = '';
    const totalPages = Math.min(pdf.numPages, 50); // Máximo 50 páginas

    for (let i = 1; i <= totalPages; i++) {
      if (progressCallback) {
        progressCallback({ 
          current: i, 
          total: totalPages, 
          status: `OCR página ${i}/${totalPages}` 
        });
      }

      const page = await pdf.getPage(i);
      const ocrText = await this.ocrPDFPage(page);
      fullText += ocrText + '\n';
    }

    if (pdf.numPages > 50) {
      fullText += '\n[Documento truncado - primeiras 50 páginas]';
    }

    return fullText;
  }

  static chunkText(text, maxChars = 4000) {
    // Dividir texto grande em chunks para processamento
    const chunks = [];
    let start = 0;

    while (start < text.length) {
      let end = start + maxChars;
      
      // Tentar quebrar em ponto final
      if (end < text.length) {
        const lastPeriod = text.lastIndexOf('.', end);
        if (lastPeriod > start) {
          end = lastPeriod + 1;
        }
      }

      chunks.push(text.substring(start, end));
      start = end;
    }

    return chunks;
  }
}

window.OCROptimizer = OCROptimizer;
