import re, sys

# Garante saida UTF-8 no Windows (evita UnicodeEncodeError com cp1252)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def audit(filename):
    with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    issues = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # Bare except
        if re.search(r'^except\s*:', stripped):
            issues.append((i, 'BARE EXCEPT', stripped))
        # print() statements (debug leftover)
        if re.search(r'^print\s*\(', stripped):
            issues.append((i, 'DEBUG print()', stripped[:120]))
        # SQL with f-string formatting (potential injection)
        if re.search(r'\.execute\s*\(\s*f["\']', stripped):
            issues.append((i, 'SQL F-STRING (possible injection)', stripped[:120]))
        # TODO/FIXME/HACK comments
        if re.search(r'#\s*(TODO|FIXME|HACK|BUG)', stripped, re.IGNORECASE):
            issues.append((i, 'TODO/FIXME/HACK', stripped[:120]))
        # conn.commit() inside except (wrong order)
        if 'commit' in stripped and 'except' in stripped:
            issues.append((i, 'COMMIT IN EXCEPT?', stripped[:120]))
    return issues

files = [
    'routes/all_routes.py',
    'routes/mural.py',
    'routes/kanban.py',
    'routes/credores.py',
    'routes/empenhos.py',
    'server.py',
    'services/openrouter_service.py',
    'services/ai_tasks.py',
]
for fname in files:
    try:
        issues = audit(fname)
        if issues:
            print('=== {} ==='.format(fname))
            for lineno, kind, text in issues:
                print('  L{} [{}]: {}'.format(lineno, kind, text))
        else:
            print('{}: OK'.format(fname))
    except FileNotFoundError:
        print('{}: FILE NOT FOUND'.format(fname))
