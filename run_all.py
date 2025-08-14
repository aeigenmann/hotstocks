import subprocess
import sys

# List of scripts to execute in order
scripts = [
    "./cleanup_files.py",
    "./fetch_and_clean_stock_list.py",
    "./fetch_stock_mentions_and_posts.py",
    "./find_hotstocks.py",
    "./extract_hotstock_posts.py",
    "./generate_reports.py",
]


def run_scripts():
    for script in scripts:
        print(f"=== Running {script} ===", flush=True)
        result = subprocess.run([sys.executable, script], stderr=subprocess.PIPE)
        if result.returncode != 0:
            print(f"❌ Error while running {script}:")
            print(result.stderr.decode("utf-8"))
            sys.exit(1)
        else:
            print()


if __name__ == "__main__":
    run_scripts()
    print("✅ All scripts completed successfully.")
