"""
Stock Symbol Post Extractor

This script processes hotstocks and posts pickle files to extract posts
that contain stock symbols from the hotstocks data. It saves matching
posts with all their comments to individual pickle files.
"""

import pickle
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# Directories
HOTSTOCKS_DIR = Path("./results/hotstocks/")
POSTS_DIR = Path("./results/posts/")
HOTSTOCKS_POSTS_DIR = Path("./results/hotstocks-posts/")
HOTSTOCKS_POSTS_DIR.mkdir(parents=True, exist_ok=True)


def get_latest_file_prefix(directory: Path, pattern: str) -> Optional[str]:
    """
    Find the latest file based on the datetime prefix in the filename.

    Args:
        directory: Directory to search in
        pattern: File pattern to match (e.g., '*_hotstocks.pkl')

    Returns:
        Latest datetime prefix or None if no files found
    """
    files = directory.glob(pattern)
    if not files:
        return None

    # Extract datetime prefixes from filenames
    prefixes = []
    for file in files:
        basename = file.name
        # Extract the datetime part (assuming format: [yyyymmdd-hhmm]_hotstocks.pkl)
        if "_" in basename:
            prefix = basename.split("_")[0]
            try:
                # Validate datetime format
                datetime.strptime(prefix, "%Y%m%d-%H%M")
                prefixes.append(prefix)
            except ValueError:
                continue

    if not prefixes:
        return None

    # Sort and return the latest
    prefixes.sort(reverse=True)
    return prefixes[0]


def load_pickle_file(filepath: Path) -> Any:
    """
    Load data from a pickle file.

    Args:
        filepath: Path to the pickle file

    Returns:
        Loaded data from pickle file

    Raises:
        FileNotFoundError: If file doesn't exist
        Exception: If pickle loading fails
    """
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    try:
        with open(filepath, "rb") as f:
            return pickle.load(f)
    except Exception as e:
        raise Exception(f"Failed to load pickle file {filepath}: {str(e)}")


def save_pickle_file(data: Any, filepath: Path) -> None:
    """
    Save data to a pickle file.

    Args:
        data: Data to save
        filepath: Path where to save the file
    """
    try:
        with open(filepath, "wb") as f:
            pickle.dump(data, f)
        print(f"Saved: {filepath}")
    except Exception as e:
        print(f"Failed to save {filepath}: {str(e)}")


def extract_stock_symbols(hotstocks_data: List[Dict]) -> Dict[str, Dict]:
    """
    Extract stock symbols and company information from hotstocks data.

    Args:
        hotstocks_data: List of hotstocks dictionaries

    Returns:
        Dictionary mapping symbols to company info
    """
    symbols = {}
    for item in hotstocks_data:
        if "symbol" in item and "company" in item:
            symbols[item["symbol"]] = {"company": item["company"], "symbol": item["symbol"]}
    return symbols


def find_matching_posts(posts_data: List[Dict], target_symbols: Dict[str, Dict]) -> Dict[str, List[Dict]]:
    """
    Find posts that contain any of the target stock symbols.

    Args:
        posts_data: List of post dictionaries
        target_symbols: Dictionary of target symbols with company info

    Returns:
        Dictionary mapping symbols to lists of matching posts
    """
    matching_posts = {symbol: [] for symbol in target_symbols.keys()}

    for post in posts_data:
        # Check if any target symbol is found in this post and it has at least 3 comments
        if post["found_symbols"] and len(post["comments"]) >= 3:
            post_symbols = post["found_symbols"].keys()
            for symbol in target_symbols.keys():
                if symbol in post_symbols:
                    matching_posts[symbol].append(post)
        # For collection posts without symbols, check whether the target symbol is found in the comments
        # Only include comments that mention the symbol or are replies to comments that do
        # Include the post if at least 3 comments match
        elif post["comments"]:
            comments = post["comments"]
            for symbol in target_symbols.keys():
                post_copy = post.copy()
                post_copy["comments"] = []  # Reset comments to only include matching ones
                for comment in comments:
                    comment_symbols = comment["found_symbols"].keys() if comment["found_symbols"] else []
                    parent_id = comment["parent_id"]
                    if symbol in comment_symbols or any(c["id"] == parent_id for c in post_copy["comments"]):
                        post_copy["comments"].append(comment)
                if len(post_copy["comments"]) >= 3:
                    matching_posts[symbol].append(post_copy)

    return matching_posts


def create_output_data(posts: List[Dict], symbol_info: Dict) -> Dict:
    """
    Create the output data structure including all posts for a symbol, comments, and symbol info.

    Args:
        posts: List of post dictionaries for the symbol
        symbol_info: Symbol and company information

    Returns:
        Complete data structure for output with all posts for the symbol
    """
    return {
        "symbol": symbol_info["symbol"],
        "company": symbol_info["company"],
        "posts": posts,
        "post_count": len(posts),
    }


def main():
    """
    Main function to process hotstocks and posts files.
    """

    # Find the latest hotstocks file
    print("Finding latest hotstocks file...")
    latest_prefix = get_latest_file_prefix(HOTSTOCKS_DIR, "*_hotstocks.pkl")

    if not latest_prefix:
        print(f"No hotstocks file found in {HOTSTOCKS_DIR}")
        return

    print(f"Latest prefix found: {latest_prefix}")

    # Construct file paths
    hotstocks_file = HOTSTOCKS_DIR / f"{latest_prefix}_hotstocks.pkl"
    posts_file = POSTS_DIR / f"{latest_prefix}_posts.pkl"

    print(f"Hotstocks file: {hotstocks_file}")
    print(f"Posts file: {posts_file}")

    # Load data files
    print("\nLoading hotstocks data...")
    hotstocks_data = load_pickle_file(hotstocks_file)
    print(f"Loaded {len(hotstocks_data)} hotstocks entries")

    print("Loading posts data...")
    posts_data = load_pickle_file(posts_file)
    print(f"Loaded {len(posts_data)} posts")

    # Extract stock symbols from hotstocks
    print("\nExtracting stock symbols...")
    target_symbols = extract_stock_symbols(hotstocks_data)
    print(f"Found {len(target_symbols)} target symbols: {list(target_symbols.keys())}")

    # Find matching posts
    print("\nSearching for matching posts...")
    matching_posts = find_matching_posts(posts_data, target_symbols)

    # Save individual files for each symbol with matches
    print("Saving matching posts...")
    total_saved = 0

    for symbol, posts in matching_posts.items():
        print(f"\nProcessing symbol: {symbol}")
        if posts:  # Only save if there are matching posts
            print(f"Found {len(posts)} matching posts")

            # Create output data with all posts for this symbol
            output_data = create_output_data(posts, target_symbols[symbol])

            # Generate filename
            filename = f"{latest_prefix}_{symbol}-posts.pkl"
            output_path = HOTSTOCKS_POSTS_DIR / filename

            # Save the file
            save_pickle_file(output_data, output_path)
            total_saved += 1
        else:
            print(f"No matching posts found for symbol: {symbol}")

    print(f"Processing complete!")
    print(f"Total files saved: {total_saved}")
    print(f"Output directory: {HOTSTOCKS_POSTS_DIR}")


if __name__ == "__main__":
    main()
