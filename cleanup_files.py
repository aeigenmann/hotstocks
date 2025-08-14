"""
File cleanup script for managing data files with timestamp prefixes.

This script performs two main operations:
1. Deletes all files in the 'stock-list' folder.
2. Keeps only the newest 30 files in other folders based on the timestamp prefix [yyyymmdd-hhmm]_.
   Files without a valid timestamp prefix are ignored and kept.
"""

import re
from datetime import datetime
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


def keep_newest_files(folder_path, max_files=30):
    """Keep only the newest files based on timestamp prefix"""
    if not folder_path.exists():
        print(f"Folder does not exist: {folder_path}")
        return

    files = [f for f in folder_path.iterdir() if f.is_file()]

    # Separate files with and without a valid timestamp
    files_with_time = []
    files_without_time = []

    for file in files:
        timestamp = parse_timestamp(file.name)
        if timestamp:
            files_with_time.append((timestamp, file))
        else:
            files_without_time.append(file)

    if len(files_with_time) <= max_files:
        print(
            f"{folder_path.name}: {len(files_with_time)} files with timestamp, no cleanup needed. {len(files_without_time)} files without timestamp were kept."
        )
        return

    # Sort files with a timestamp (newest first)
    files_with_time.sort(key=lambda x: x[0], reverse=True)

    # Keep the newest files with a timestamp
    files_to_keep = files_with_time[:max_files]
    files_to_delete = files_with_time[max_files:]

    # Delete the excess timestamped files
    for _, file in files_to_delete:
        file.unlink()
        print(f"Deleted: {file.name}")

    print(
        f"{folder_path.name}: kept {len(files_to_keep)} files with timestamp, deleted {len(files_to_delete)} files. {len(files_without_time)} files without timestamp were kept."
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

    # Keep newest 30 files in other folders
    for folder_name in ["hotstocks", "hotstocks-posts", "mentions", "posts", "hotstocks-reports"]:
        keep_newest_files(results_dir / folder_name)

    print("Cleanup completed!")


if __name__ == "__main__":
    main()
