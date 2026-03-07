(function () {
  async function saveBlob(blob, options = {}) {
    const nome = options.nome || 'arquivo-gerado.bin';
    const categoria = options.categoria || 'gerados';
    const referencia = options.referencia || '';
    const descricao = options.descricao || '';
    const file = new File([blob], nome, { type: blob.type || 'application/octet-stream' });
    const fd = new FormData();
    fd.append('nome', nome);
    fd.append('categoria', categoria);
    fd.append('referencia', referencia);
    fd.append('descricao', descricao);
    fd.append('arquivo', file);
    const res = await fetch('/api/documentos/conteudo', { method: 'POST', body: fd });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || 'Falha ao salvar documento gerado');
    return data;
  }

  async function saveText(text, options = {}) {
    const blob = new Blob([text], { type: options.mimeType || 'text/plain;charset=utf-8;' });
    return saveBlob(blob, options);
  }

  function downloadBlob(blob, fileName) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  window.DocumentAutosave = {
    saveBlob,
    saveText,
    downloadBlob,
  };
})();
