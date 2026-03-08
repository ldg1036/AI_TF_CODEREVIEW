"""Remove extracted Mixin methods from server.py and add Mixin imports."""
import re

INPUT = r"d:\AI_TF_CODEREVIEW-main\backend\server.py"
OUTPUT = INPUT  # overwrite

# Methods to remove (name -> approximate marker)
METHODS_TO_REMOVE = [
    # AnalyzeJobMixin methods
    "_prune_analyze_jobs",
    "_compute_eta_ms",
    "_refresh_job_timing_locked",
    "_public_analyze_job_view",
    "_run_analyze_job",
    "_handle_analyze_start",
    "_handle_analyze_status",
    # RequestValidationMixin methods
    "_parse_analyze_request_body",
    "_analysis_response_status",
    "_autofix_error_payload",
    "_read_json_body",
    "_is_txt",
    "_is_normalized_txt",
    "_validate_selected_files",
    "_is_local_absolute_path",
    "_is_supported_input_file",
    "_folder_has_supported_targets",
    "_validate_input_sources",
    "_read_multipart_files",
    # HealthCheckMixin methods
    "_playwright_dependency_status",
    "_build_dependency_health_payload",
    "_resolve_latest_verification_summary",
]

# Also remove class variables that moved to AnalyzeJobMixin
CLASS_VARS_TO_REMOVE = [
    "_analyze_jobs:",
    "_analyze_jobs_lock",
    "_analyze_job_ttl_sec",
    "_analyze_job_max_entries",
    "_analyze_poll_interval_ms",
]

with open(INPUT, "r", encoding="utf-8") as f:
    lines = f.readlines()

print(f"Original: {len(lines)} lines")

# Find method boundaries
def find_method_ranges(lines, method_names):
    """Find (start, end) line ranges for each method."""
    ranges = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        # Match method definitions (def, @staticmethod, @classmethod decorators)
        for name in method_names:
            if f"def {name}(" in stripped or f"def {name} (" in stripped:
                # Look back for decorators
                start = i
                while start > 0 and lines[start - 1].strip().startswith("@"):
                    start -= 1
                # Find method end: next line at same or lower indentation that isn't blank
                method_indent = len(line) - len(line.lstrip())
                end = i + 1
                while end < len(lines):
                    next_line = lines[end]
                    next_stripped = next_line.strip()
                    if next_stripped == "":
                        end += 1
                        continue
                    next_indent = len(next_line) - len(next_line.lstrip())
                    if next_indent <= method_indent and not next_stripped.startswith("#"):
                        break
                    end += 1
                # Trim trailing blank lines
                while end > start and lines[end - 1].strip() == "":
                    end -= 1
                ranges.append((name, start, end))
                break
        i += 1
    return ranges

method_ranges = find_method_ranges(lines, METHODS_TO_REMOVE)

# Find class variable lines to remove
var_lines_to_remove = set()
for i, line in enumerate(lines):
    stripped = line.strip()
    for var in CLASS_VARS_TO_REMOVE:
        if var in stripped and i < 130:  # Only in class header area
            var_lines_to_remove.add(i)

# Build set of lines to remove
lines_to_remove = set(var_lines_to_remove)
for name, start, end in method_ranges:
    print(f"  {name}: lines {start+1}-{end} ({end - start} lines)")
    for j in range(start, end):
        lines_to_remove.add(j)

print(f"Found {len(method_ranges)} methods to remove")
print(f"Found {len(var_lines_to_remove)} class variable lines to remove")
print(f"Total lines to remove: {len(lines_to_remove)}")

# Build new file
new_lines = []
for i, line in enumerate(lines):
    if i not in lines_to_remove:
        new_lines.append(line)

# Clean up consecutive blank lines (max 2)
final_lines = []
blank_count = 0
for line in new_lines:
    if line.strip() == "":
        blank_count += 1
        if blank_count <= 2:
            final_lines.append(line)
    else:
        blank_count = 0
        final_lines.append(line)

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.writelines(final_lines)

print(f"Done. New file: {len(final_lines)} lines (removed {len(lines) - len(final_lines)})")
