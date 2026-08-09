import os

pnl_path = r'C:\Users\39145\Downloads\Coder_Wincc-main\CodeReview_Data\새 폴더\CA2_Na2SO3_VALVE.pnl'

with open(pnl_path, 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

print(f"Total lines in PNL: {len(lines)}")

# Extract script parts or line details
scripts_found = []
current_script = []
in_script = False
start_line = 0

for i, line in enumerate(lines, 1):
    if "SCRIPT" in line or "main()" in line or "scope" in line:
        # trace lines with code
        pass

# Save extracted source code preview to secondary_data
secondary_path = os.path.join('secondary_data', 'extracted_pnl_code.txt')
with open(secondary_path, 'w', encoding='utf-8') as f:
    for i, line in enumerate(lines, 1):
        f.write(f"{i:4d}: {line}")

print(f"Extracted PNL code saved to {secondary_path}")
