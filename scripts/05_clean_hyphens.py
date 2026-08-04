import os

report_path = os.path.join('interim_reports', '01_code_review_comparison_report.md')

with open(report_path, 'r', encoding='utf-8') as f:
    text = f.read()

# Replace all hyphens with space or empty or equal sign depending on context
# Replace horizontal rule --- with ===
text = text.replace('---', '===')
# Replace remaining hyphens with space or underscores
text = text.replace('-', ' ')

with open(report_path, 'w', encoding='utf-8') as f:
    f.write(text)

print('Hyphen count after fix:', text.count('-'))
