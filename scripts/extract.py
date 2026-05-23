import re
with open('pages/tarefas.html', 'r', encoding='utf-8', errors='ignore') as f:
    text = f.read()

matches = re.findall(r'(async function loadTasks\(\)[\s\S]*?)(?=\n\s*async function|\n\s*function|// ──)', text)
if not matches:
    matches = re.findall(r'(function loadTasks\(\)[\s\S]*?)(?=\n\s*async function|\n\s*function|// ──)', text)

with open('load_tasks.txt', 'w', encoding='utf-8') as fw:
    if matches:
        fw.write(matches[0][:4000])
    else:
        # Just find the fetch call
        m2 = re.findall(r'([\s\S]{0,1000}fetch\([\'"`]/api/kanban[\'"`]\)[\s\S]{0,2000})', text)
        if m2: fw.write(m2[0])
        else: fw.write("Not found")
