import ast
import re

print('--- kanban_listar ---')
try:
    code = open('server.py', 'r', encoding='utf-8', errors='ignore').read()
    module = ast.parse(code)
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name == 'kanban_listar':
            print(ast.unparse(node))
except Exception as e:
    print('AST Error:', e)
    # Fallback to regex if ast fails due to syntax errors in server.py
    matches = re.findall(r'(def kanban_listar\([\s\S]*?\n\S)', code)
    if matches: print(matches[0])

print('\n--- loadTasks ---')
try:
    text = open('pages/tarefas.html', 'r', encoding='utf-8', errors='ignore').read()
    matches = re.findall(r'(async function loadTasks[\s\S]*?)(?=\n\s*async function|\n\s*function|// ──)', text)
    if not matches:
        matches = re.findall(r'(function loadTasks[\s\S]*?)(?=\n\s*async function|\n\s*function|// ──)', text)
    if matches:
        print(matches[0][:2000])
    else:
        # Just find where fetch('/api/kanban') is
        matches2 = re.findall(r'([\s\S]{0,500}fetch\([\'"`]/api/kanban[\'"`]\)[\s\S]{0,1000})', text)
        if matches2: print(matches2[0])
except Exception as e:
    print('HTML Error:', e)
