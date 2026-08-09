import os

file_path = os.path.join('secondary_data', 'extracted_pnl_code.txt')

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

code_blocks = []
keywords = ['dpConnect', 'dpGet', 'dpSet', 'dpQuery', 'main', 'void', 'int', 'string', 'bool', 'if', 'while', 'for', 'switch', 'case', 'CB_']

for i, line in enumerate(lines, 1):
    for kw in keywords:
        if kw in line:
            code_blocks.append((i, line.strip()))
            break

print(f"Total lines matching keywords: {len(code_blocks)}")
for line_num, content in code_blocks[:50]:
    print(f"L{line_num}: {content}")
