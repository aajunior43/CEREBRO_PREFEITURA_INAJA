"""
Analisa o consumo de RAM estimado do server.py:
- _file_cache: raw bytes de cada arquivo
- _gzip_cache: versao gzip comprimida
- _brotli_cache: versao brotli comprimida
- _etag_cache: hash MD5 16 chars por arquivo
- _file_mtime_cache: float por arquivo

Além disso verifica quais arquivos sao incluidos/excluidos.
"""
import os, gzip, mimetypes

BASE_DIR = r'j:\CEREBRO_PREFEITURA_INAJA-main\CEREBRO_PREFEITURA_INAJA-main'

SKIP_EXTS = {'.db', '.db-shm', '.db-wal', '.pyc', '.pyo', '.log', '.bat'}
SKIP_DIRS = {'__pycache__', '.git', 'DADOS', 'renomer', 'documentos_centro',
             'PARA IMPLEMENTAR TODO ESSE PROJETO NO PROJETO PRINCIPAL',
             '.vscode', '.pytest_cache', '.backup_worktree', 'pref_extracted',
             'logs', 'tests', 'app', 'services', 'routes', 'scripts'}

COMPRESSIBLE = {
    'text/html', 'text/css', 'text/javascript', 'application/javascript',
    'application/json', 'image/svg+xml', 'text/plain', 'text/xml'
}

raw_total = 0
gz_total = 0
file_count = 0
top_files = []

print("=== ARQUIVOS CARREGADOS NO CACHE RAM ===\n")
print(f"{'Arquivo':<55} {'Raw':>10} {'Gzip':>10} {'Tipo'}")
print("-"*95)

for root, dirs, files in os.walk(BASE_DIR):
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith('.')]
    rel_root = os.path.relpath(root, BASE_DIR).replace('\\', '/')
    if rel_root == '.':
        rel_root = ''

    for fname in files:
        ext = os.path.splitext(fname)[1].lower()
        if ext in SKIP_EXTS:
            continue
        fpath = os.path.join(root, fname)
        url = ('/' + rel_root + '/' + fname).replace('//', '/')
        try:
            with open(fpath, 'rb') as f:
                data = f.read()
            raw_size = len(data)
            raw_total += raw_size
            file_count += 1

            mime, _ = mimetypes.guess_type(fpath)
            mime = mime or 'application/octet-stream'
            base_mime = mime.split(';')[0].strip()

            gz_size = 0
            if base_mime in COMPRESSIBLE and raw_size > 256:
                gz_data = gzip.compress(data, compresslevel=6)
                gz_size = len(gz_data)
                gz_total += gz_size

            top_files.append((raw_size, gz_size, url))
            print(f"  {url:<53} {raw_size/1024:>8.1f}KB {gz_size/1024:>8.1f}KB  {base_mime}")
        except OSError as e:
            print(f"  ERRO: {url} → {e}")

print("\n" + "="*95)
print(f"\n{'Total de arquivos:':<35} {file_count}")
print(f"{'RAM usada (raw bytes):':<35} {raw_total/1024/1024:.2f} MB")
print(f"{'RAM usada (gzip cache):':<35} {gz_total/1024/1024:.2f} MB")
print(f"{'RAM usada (brotli ~= gzip):':<35} {gz_total/1024/1024:.2f} MB  (estimado)")
print(f"{'TOTAL RAM estimada (raw+gz+br):':<35} {(raw_total + gz_total*2)/1024/1024:.2f} MB")

print("\n=== TOP 10 MAIORES ARQUIVOS NO CACHE ===")
top_files.sort(reverse=True)
for raw_size, gz_size, url in top_files[:10]:
    print(f"  {raw_size/1024:>8.1f}KB raw  {gz_size/1024:>8.1f}KB gzip  {url}")
