import re
css = open('static/css/index.css', 'r', encoding='utf-8').read()

print("MARGIN LEFT:")
for m in re.finditer(r'([a-zA-Z0-9_.,\#:>\s-]+)\{[^}]*margin-left:[^}]*\}', css):
    print(m.group(1).strip())

print("\nPADDING LEFT:")
for m in re.finditer(r'([a-zA-Z0-9_.,\#:>\s-]+)\{[^}]*padding-left:[^}]*\}', css):
    print(m.group(1).strip())
