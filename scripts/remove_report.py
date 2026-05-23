import re
f = 'pages/tarefas.html'
with open(f, 'r', encoding='utf-8') as file:
    text = file.read()

# removing the kb-report-panel div which ends before kb-cat-filter
new_text = re.sub(r'(\s*)<div class="kb-report-panel">[\s\S]*?(?=\s*<div class="kb-cat-filter">)', r'\1', text)

with open(f, 'w', encoding='utf-8') as file:
    file.write(new_text)

print('Changed:', text != new_text)
