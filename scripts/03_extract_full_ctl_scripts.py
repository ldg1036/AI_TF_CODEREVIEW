import os

file_path = os.path.join('secondary_data', 'extracted_pnl_code.txt')

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

output_script_path = os.path.join('secondary_data', 'all_scripts_only.ctl')

with open(output_script_path, 'w', encoding='utf-8') as out:
    for line in lines:
        # Check line number header format "i: line"
        parts = line.split(':', 1)
        if len(parts) == 2:
            line_num_str, content = parts[0], parts[1]
            out.write(f"/* L{line_num_str.strip()} */ {content}")

print(f"Full script extracted to {output_script_path}")
