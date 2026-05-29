"""
Analisa o consumo de RAM com as mesmas regras do server.py atualizado.
"""
import os, gzip, mimetypes

BASE_DIR = r'j:\CEREBRO_PREFEITURA_INAJA-main\CEREBRO_PREFEITURA_INAJA-main'

# NOVAS regras do server.py (apos a correcao)
SKIP_EXTS = {
    ".db", ".db-shm", ".db-wal",
    ".pyc", ".pyo",
    ".log", ".bat", ".ps1", ".sh",
    ".exe", ".dll", ".so", ".bin",
    ".zip", ".gz", ".tar", ".rar", ".7z",
    ".ttf", ".otf", ".eot",
    ".py", ".md", ".txt", ".rst",
    ".csv",
}
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

for root, dirs, files in os.walk(BASE_DIR):
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith('.')]
    rel_root = os.path.relpath(root, BASE_DIR).replace('\\', '/')
    if rel_root == '.': rel_root = ''
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
        except OSError:
            pass

print(f"Total de arquivos no cache: {file_count}")
print(f"RAM raw:                    {raw_total/1024/1024:.2f} MB")
print(f"RAM gzip cache:             {gz_total/1024/1024:.2f} MB")
print(f"RAM brotli cache (estimado):{gz_total/1024/1024:.2f} MB")
print(f"TOTAL RAM estimado:         {(raw_total + gz_total*2)/1024/1024:.2f} MB")
print()
print("TOP 10 maiores no cache:")
top_files.sort(reverse=True)
for raw_size, gz_size, url in top_files[:10]:
    print(f"  {raw_size/1024:>8.1f}KB raw  {gz_size/1024:>8.1f}KB gz  {url}")
