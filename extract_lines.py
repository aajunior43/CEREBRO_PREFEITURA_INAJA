lines = open('pages/tarefas.html', 'r', encoding='utf-8', errors='ignore').readlines()
start = -1
for i, l in enumerate(lines):
    if 'function renderBoard(' in l:
        start = i
        break
if start != -1:
    with open('render_board.txt', 'w', encoding='utf-8') as f:
        for i in range(start, min(start + 150, len(lines))):
            f.write(lines[i])
