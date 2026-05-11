import re

print('--- SERVER.PY ROUTES ---')
with open('server.py', 'r', encoding='utf-8', errors='ignore') as f:
    text = f.read()
    routes = re.findall(r'@app\.route\([^)]+\)[\s\S]*?def \w+', text)
    for r in routes:
        if 'kanban' in r.lower() or 'tarefa' in r.lower() or 'task' in r.lower():
            print(r)

print('\n--- TAREFAS.HTML FETCHES ---')
with open('pages/tarefas.html', 'r', encoding='utf-8', errors='ignore') as f:
    text = f.read()
    fetches = set(re.findall(r'fetch\([\'"`]([^\'"`]+)[\'"`]', text))
    for fetch in fetches:
        if 'api' in fetch.lower() or 'kanban' in fetch.lower() or 'tarefa' in fetch.lower() or 'task' in fetch.lower():
            print(fetch)
