"""
File cleanup script for managing data files with timestamp prefixes.

This script performs two main operations:
1. Deletes all files in the 'stock-list' folder.
2. Keeps only the newest 30 files in other folders based on the timestamp prefix [yyyymmdd-hhmm]_.
   Files without a valid timestamp prefix are ignored and kept.
"""

import re
from datetime import datetime, timedelta
from pathlib import Path


PREFIX_PATTERN = re.compile(r"^(\d{8}-\d{4})_")


def parse_timestamp(filename):
    """Extract timestamp from filename with format [yyyymmdd-hhmm]_*"""
    match = PREFIX_PATTERN.match(filename)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y%m%d-%H%M")
        except ValueError:
            pass
    return None


def delete_all_files(folder_path):
    """Delete all files in the specified folder"""
    if not folder_path.exists():
        print(f"Folder does not exist: {folder_path}")
        return

    files = [f for f in folder_path.iterdir() if f.is_file()]
    for file in files:
        file.unlink()
        print(f"Deleted: {file.name}")

    print(f"Deleted {len(files)} files from {folder_path.name}")


def keep_newest_files(folder_path, max_days=30):
    """Keep only files from the last N days based on timestamp prefix."""
    if not folder_path.exists():
        print(f"Folder does not exist: {folder_path}")
        return

    files = [f for f in folder_path.iterdir() if f.is_file()]
    cutoff_date = datetime.now() - timedelta(days=max_days)

    files_to_delete = []
    kept_files_with_timestamp = 0
    files_without_timestamp = 0

    for file in files:
        timestamp = parse_timestamp(file.name)
        if timestamp:
            if timestamp < cutoff_date:
                files_to_delete.append(file)
            else:
                kept_files_with_timestamp += 1
        else:
            files_without_timestamp += 1

    if not files_to_delete:
        print(
            f"{folder_path.name}: No files older than {max_days} days found. Kept {kept_files_with_timestamp} timestamped files and {files_without_timestamp} other files."
        )
        return

    # Delete the old files
    for file in files_to_delete:
        file.unlink()
        print(f"Deleted: {file.name}")

    print(
        f"{folder_path.name}: Kept {kept_files_with_timestamp} files from the last {max_days} days, deleted {len(files_to_delete)} old files. {files_without_timestamp} files without timestamp were kept."
    )


def main():
    """Execute the file cleanup operations"""
    print("Starting file cleanup...")

    results_dir = Path("results")
    if not results_dir.exists():
        print(f"Results directory not found: {results_dir}")
        return

    # Delete all files in stock-list
    delete_all_files(results_dir / "stock-list")

    # Keep only files from the last 30 days in other folders
    for folder_name in [
        "hotstocks",
        "hotstocks-posts",
        "mentions",
        "posts",
        "hotstocks-reports",
    ]:
        keep_newest_files(results_dir / folder_name)

    print("Cleanup completed!")


if __name__ == "__main__":
    main()
