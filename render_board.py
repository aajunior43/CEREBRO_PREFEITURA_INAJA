import re
text = open('pages/tarefas.html', 'r', encoding='utf-8', errors='ignore').read()
matches = re.findall(r'(function renderBoard\(\)[\s\S]*?\n\s*\})', text)

with open('render_board.txt', 'w', encoding='utf-8') as fw:
    if matches:
        # get the first that seems to be the full function
        for m in matches:
            if len(m) > 100:
                fw.write(m)
                break
    else:
        fw.write("Not found")
