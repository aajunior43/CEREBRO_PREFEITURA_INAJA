css = open('static/css/index.css', 'r', encoding='utf-8').read()
blocks = css.split('}')
interesting = []
for block in blocks:
    if '.main-content {\n' in block or '.app-sidebar {\n' in block or 'body {\n' in block or '.empenhos-list' in block:
        interesting.append(block + '}')
with open('debug_css.txt', 'w', encoding='utf-8') as f:
    f.write('\n\n'.join(interesting))
