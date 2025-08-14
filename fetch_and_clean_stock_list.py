import pandas as pd
from pathlib import Path
import csv

# Directories
OUTPUT_DIR = Path("./results/stock-list/")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------
# --- Helper Function ---
# ------------------------------------------------------------
def create_name_key(series, column_name):
    """
    Create a 'NameKey' from the first two words of a company/security name (lowercase).
    This helps identify duplicates where the full name may differ slightly
    but represents the same company.
    """
    return series[column_name].str.strip().str.split().str[:2].str.join(" ").str.lower()


# ------------------------------------------------------------
# --- NASDAQ Data ---
# ------------------------------------------------------------
nasdaq_url = "https://nasdaqtrader.com/dynamic/symdir/nasdaqlisted.txt"
nasdaq = pd.read_csv(nasdaq_url, sep="|", comment="#", dtype=str, na_filter=False)

# Keep only non-ETF listings
nasdaq = nasdaq[nasdaq["ETF"] == "N"]

# Create a NameKey for duplicate detection
nasdaq["NameKey"] = create_name_key(nasdaq, "Security Name")

# Keep the first unique entry for each NameKey
nasdaq_unique = nasdaq.drop_duplicates(subset=["NameKey"], keep="first")

# Keep only relevant columns and rename for consistency
nasdaq_unique = nasdaq_unique[["Symbol", "Security Name"]].rename(columns={"Security Name": "Company Name"})

# ------------------------------------------------------------
# --- NYSE Data ---
# ------------------------------------------------------------
nyse_url = "https://datahub.io/core/nyse-other-listings/r/nyse-listed.csv"
nyse = pd.read_csv(nyse_url, dtype=str, na_filter=False)

# Create a NameKey for duplicate detection
nyse["NameKey"] = create_name_key(nyse, "Company Name")

# Keep the first unique entry for each NameKey
nyse_unique = nyse.drop_duplicates(subset=["NameKey"], keep="first")

# Keep only relevant columns and rename for consistency
nyse_unique = nyse_unique[["ACT Symbol", "Company Name"]].rename(columns={"ACT Symbol": "Symbol"})

# ------------------------------------------------------------
# --- Combine NASDAQ and NYSE ---
# ------------------------------------------------------------
all_stocks_df = pd.concat([nasdaq_unique, nyse_unique], ignore_index=True)

# List of special symbols that should have a "$" prefix
special_symbols = {
    "BE",
    "GO",
    "IT",
    "OR",
    "SO",
    "NO",
    "UP",
    "FOR",
    "ON",
    "BY",
    "AS",
    "HE",
    "AM",
    "AN",
    "AI",
    "DD",
    "OP",
    "ALL",
    "YOU",
    "TV",
    "PM",
    "HAS",
    "ARM",
    "ARE",
    "PUMP",
    "EOD",
    "DAY",
    "WTF",
    "HIT",
    "NOW",
}

# Apply "$" prefix if:
# - Symbol is 1 character long, OR
# - Symbol is in the special_symbols set
all_stocks_df["Symbol"] = all_stocks_df["Symbol"].apply(
    lambda s: f"${s}" if len(str(s)) == 1 or str(s) in special_symbols else s
)

# Remove duplicates across exchanges based on full company name
all_stocks_df = all_stocks_df.sort_values(by=["Company Name", "Symbol"]).drop_duplicates(
    subset=["Company Name"], keep="first"
)

# Optionally remove duplicate symbols
all_stocks_df = all_stocks_df.drop_duplicates(subset=["Symbol"])

# Convert to plain Python list of dicts
symbol_company_list = [
    {"symbol": symbol, "company": company} for symbol, company in all_stocks_df[["Symbol", "Company Name"]].to_numpy()
]

# ------------------------------------------------------------
# --- Save Results ---
# ------------------------------------------------------------

# Save as Pickle (symbols and names)
pd.to_pickle(symbol_company_list, OUTPUT_DIR / "cleaned-stock-list.pkl")

# Save as CSV for inspection
with open(OUTPUT_DIR / "cleaned-stock-list.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["symbol", "company"])
    writer.writeheader()
    writer.writerows(symbol_company_list)


# ------------------------------------------------------------
# --- Summary Output ---
# ------------------------------------------------------------
print(f"NASDAQ before: {len(nasdaq)} | after: {len(nasdaq_unique)}")
print(f"NYSE before: {len(nyse)} | after: {len(nyse_unique)}")
print(f"Final combined list: {len(all_stocks_df)} entries saved")
