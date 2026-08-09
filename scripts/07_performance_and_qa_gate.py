import os
import subprocess
import time


def run_qa_gate():
    print("=== WinCC OA Code Reviewer Release QA Gate Inspection ===")

    # 1. Run Pytest Suite
    start_time = time.time()
    result = subprocess.run(['pytest', 'tests/'], cwd='wincc_reviewer', capture_output=True, text=True)
    duration = time.time() - start_time

    print(f"Pytest Duration: {duration:.2f} seconds")
    print(f"Pytest Return Code: {result.returncode}")

    # 2. Check Build Output Artifacts
    dist_exe = os.path.join('wincc_reviewer', 'dist', 'WinCC_OA_Code_Reviewer', 'WinCC_OA_Code_Reviewer.exe')
    exe_exists = os.path.exists(dist_exe)
    print(f"Executable Exists: {exe_exists} at {dist_exe}")

if __name__ == '__main__':
    run_qa_gate()
