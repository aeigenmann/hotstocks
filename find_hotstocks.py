import os
from pathlib import Path
import re
import pickle
import csv
from datetime import datetime

# Directories
MENTIONS_DIR = Path("./results/mentions/")
HOTSTOCKS_DIR = Path("./results/hotstocks/")
HOTSTOCKS_DIR.mkdir(parents=True, exist_ok=True)

# Regex to match the file naming pattern
FILENAME_PATTERN = re.compile(r"^(\d{8}-\d{4})_mentions\.pkl$")


def load_pickle(filepath):
    """Load a pickle file and return its content."""
    with open(filepath, "rb") as f:
        return pickle.load(f)


def list_to_dict(data_list):
    """
    Convert a list of dicts (with symbol, company, count) into a dictionary
    keyed by symbol for easier comparison.
    """
    return {item["symbol"]: {"company": item["company"], "count": item["count"]} for item in data_list}


def get_latest_three_files():
    """Return the three most recent result files sorted by timestamp."""
    files = []
    for fname in os.listdir(MENTIONS_DIR):
        match = FILENAME_PATTERN.match(fname)
        if match:
            timestamp_str = match.group(1)
            try:
                ts = datetime.strptime(timestamp_str, "%Y%m%d-%H%M")
                files.append((ts, fname))
            except ValueError:
                pass  # Ignore invalid timestamps
    files.sort(key=lambda x: x[0], reverse=True)
    return files[:3]


def compare_files(latest_data, prev_data, prev2_data):
    """
    Compare latest file with the previous two to find hot stocks.
    Includes company name in the result.
    Returns a list of dicts sorted by latest count.
    """
    hotstocks = []

    # Get the union of all symbols across the three files
    all_symbols = set(latest_data) | set(prev_data) | set(prev2_data)

    for symbol in all_symbols:
        latest_val = latest_data.get(symbol, {"count": 0})["count"]
        prev_val = prev_data.get(symbol, {"count": 0})["count"]
        prev2_val = prev2_data.get(symbol, {"count": 0})["count"]

        company_name = (latest_data.get(symbol) or prev_data.get(symbol) or prev2_data.get(symbol))["company"]

        # Condition 1: latest > previous
        cond1 = latest_val > prev_val

        # Condition 2: latest > average of previous two
        avg_prev = (prev_val + prev2_val) / 2
        cond2 = latest_val > avg_prev

        if cond1 or cond2:
            hotstocks.append(
                {"symbol": symbol, "company": company_name, "latest": latest_val, "prev": prev_val, "prev2": prev2_val}
            )

    # Sort by latest count descending
    return sorted(hotstocks, key=lambda x: x["latest"], reverse=True)


def save_pickle(data, filepath):
    """Save data to a pickle file."""
    with open(filepath, "wb") as f:
        pickle.dump(data, f)
        print(data)


def save_csv(data, filepath):
    """Save data to a CSV file."""
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["symbol", "company", "latest", "prev", "prev2"])
        writer.writeheader()
        writer.writerows(data)


def main():
    latest_three = get_latest_three_files()
    if len(latest_three) < 3:
        print("Not enough files to compare. Need at least 3.")
        return

    # Sort newest first
    lates_t_ts, latest_fname = latest_three[0]
    prev_ts, prev_fname = latest_three[1]
    prev2_ts, prev2_fname = latest_three[2]

    # Load pickle contents
    latest_data = list_to_dict(load_pickle(MENTIONS_DIR / latest_fname))
    prev_data = list_to_dict(load_pickle(MENTIONS_DIR / prev_fname))
    prev2_data = list_to_dict(load_pickle(MENTIONS_DIR / prev2_fname))

    # Compare and find hot stocks
    hotstocks = compare_files(latest_data, prev_data, prev2_data)

    # Base filename for both pickle and CSV
    base_name = latest_fname.replace("_mentions.pkl", "_hotstocks")
    pickle_path = HOTSTOCKS_DIR / f"{base_name}.pkl"
    csv_path = HOTSTOCKS_DIR / f"{base_name}.csv"

    # Save both files
    save_pickle(hotstocks, pickle_path)
    save_csv(hotstocks, csv_path)

    print(f"Hot stocks saved to: {pickle_path}")
    print(f"Number of hot stocks: {len(hotstocks)}")


if __name__ == "__main__":
    main()
