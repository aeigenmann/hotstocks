import pickle
import praw
import requests
import re
from datetime import datetime, timedelta
from collections import defaultdict
from dotenv import load_dotenv
import os
from pathlib import Path
import csv

# Directories
STOCK_LIST_DIR = Path("./results/stock-list/")
MENTIONS_DIR = Path("./results/mentions/")
MENTIONS_DIR.mkdir(parents=True, exist_ok=True)
POSTS_DIR = Path("./results/posts/")
POSTS_DIR.mkdir(parents=True, exist_ok=True)


def load_symbols():
    """
    Loads stock symbols and company names from the pickle file.
    Returns:
        symbols_list: List of stock symbol strings
        symbol_to_company: Dict mapping symbol -> company name
    """
    with open(STOCK_LIST_DIR / "cleaned-stock-list.pkl", "rb") as f:
        data = pickle.load(f)

    # Extract symbol strings for text matching
    symbols_list = [entry["symbol"] for entry in data]

    # Create a dictionary to quickly look up company name by symbol
    symbol_to_company = {entry["symbol"]: entry["company"] for entry in data}

    return symbols_list, symbol_to_company


def setup_reddit():
    """Initializes Reddit API connection"""
    load_dotenv("./reddit_secret.env")
    session = requests.Session()
    # session.verify = False  # Disable SSL verification (not recommended in production)
    return praw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        user_agent=os.getenv("REDDIT_USER_AGENT"),
        requestor_kwargs={"session": session},
    )


def find_symbols_in_text(text, pattern):
    """
    Finds a large number of symbols in a given text using a single, optimized regex.
    Returns:
        dict: A dictionary with symbols as keys and their occurrence count as values.
    """
    found = defaultdict(int)

    # Find all matches in the text in a single pass
    matches = pattern.findall(text, re.IGNORECASE is False)
    for match in matches:
        # The second group (match[1]) contains the actual symbol without the '$' prefix
        symbol = match[1]
        found[symbol] += 1

    return found


def get_comment_hierarchy(comment):
    """
    Determines hierarchy information of a comment.
    Returns:
        (parent_id, depth) where:
            - parent_id is None for top-level comments
            - depth is 0 for top-level, >0 for replies
    """
    if comment.is_root:
        return None, 0
    else:
        depth = 1
        current = comment
        while hasattr(current, "parent") and not current.parent().is_root:
            try:
                current = current.parent()
                depth += 1
            except:
                break
        parent_id = comment.parent_id.split("_")[1]  # Remove "t1_" or "t3_" prefix
        return parent_id, depth


def save_posts_data(posts_data, run_id):
    """
    Saves posts and comments to a separate pickle file
    Format: List of dictionaries containing post and comment data
    """
    filename = POSTS_DIR / f"{run_id}_posts.pkl"
    with open(filename, "wb") as f:
        pickle.dump(posts_data, f)
    print(f"📝 Posts data saved to: {filename}")
    return filename


def scan_wsb_mentions():
    """Main function to scan r/wallstreetbets for stock mentions"""
    # Generate unique run ID
    run_id = datetime.now().strftime("%Y%m%d-%H%M")
    print(f"Starting crawler with ID: {run_id}")

    # Initialize
    symbols, symbol_to_company = load_symbols()
    reddit = setup_reddit()
    total_counts = defaultdict(int)
    posts_data = []

    # Escape special characters in symbols to prevent regex errors
    escaped_symbols = [re.escape(symbol) for symbol in symbols]
    # Create a single pattern by joining all escaped symbols with the OR operator (|)
    # The pattern matches "$SYMBOL" or "SYMBOL" as a whole word.
    pattern_string = "|".join(escaped_symbols)
    pattern = re.compile(rf"\b(\$)?({pattern_string})\b")

    # Load subreddit
    wsb = reddit.subreddit("wallstreetbets")
    cutoff_time = datetime.now() - timedelta(days=1)

    print(f"Scanning posts from last 24h in r/wallstreetbets...")

    # Scan new posts (last 24h)
    for post in wsb.new(limit=100):  # Limit adjustable
        post_time = datetime.fromtimestamp(post.created_utc)
        if post_time < cutoff_time:
            continue
        if post.score < 3:
            continue  # Skip low-upvote posts

        print(f"📄 Post: {post.title[:50]}...")

        # Search post title and text
        combined_text = f"{post.title} {post.selftext}"
        post_findings = find_symbols_in_text(combined_text, pattern)
        if post_findings:
            print(f"  ✓ Found in post: {dict(post_findings)}")
            for symbol, count in post_findings.items():
                total_counts[symbol] += count

        # Collect post data for later storage
        post_data = {
            "type": "post",
            "id": post.id,
            "title": post.title,  # Complete post title
            "content": post.selftext,  # Complete post content
            "upvotes": post.score,
            "created_utc": post.created_utc,
            "url": f"https://www.reddit.com{post.permalink}",
            "found_symbols": dict(post_findings),
            "comments": [],  # List for qualified comments
        }

        # Search comments
        try:
            total_comment_findings = defaultdict(int)
            post.comments.replace_more(limit=32)  # Limit number of "MoreComments" objects
            for comment in post.comments.list():
                if comment.score < 3:
                    continue  # Skip low-upvote comments

                comment_findings = find_symbols_in_text(comment.body, pattern)
                # Determine hierarchy information
                parent_id, depth = get_comment_hierarchy(comment)
                if comment_findings:
                    for symbol, count in comment_findings.items():
                        total_counts[symbol] += count
                        total_comment_findings[symbol] += count

                # Save comments with stock relevance
                if (
                    post_data["found_symbols"]
                    or comment_findings
                    or any(c["id"] == parent_id for c in post_data["comments"])
                ):
                    comment_data = {
                        "type": "comment",
                        "id": comment.id,
                        "body": comment.body,  # Complete comment text
                        "upvotes": comment.score,
                        "created_utc": comment.created_utc,
                        "parent_id": parent_id,  # None for top-level, else parent comment ID
                        "hierarchy_depth": depth,  # 0 for top-level, >0 for replies
                        "is_reply": not comment.is_root,  # Bool: Is reply to another comment?
                        "found_symbols": (dict(comment_findings) if comment_findings else {}),
                    }
                    post_data["comments"].append(comment_data)

            if total_comment_findings:
                print(f"  ✓ Found in comments: {dict(total_comment_findings)}")

        except Exception as e:
            print(f"  ⚠️ Error with comments: {e}")

        # Add post data to overall list (only if post or comments are relevant)
        if post_data["found_symbols"] or post_data["comments"]:
            posts_data.append(post_data)

    # Save posts data (independent of symbol frequency)
    if posts_data:
        save_posts_data(posts_data, run_id)

        # Statistics about saved posts data
        total_posts = len(posts_data)
        total_comments = sum(len(post["comments"]) for post in posts_data)
        print(f"📊 Saved posts data: {total_posts} posts, {total_comments} comments (≥3 upvotes)")

    # Filter results (>=10 mentions)
    filtered_results = [
        {
            "symbol": symbol,
            "company": symbol_to_company.get(symbol, "Unknown Company"),
            "count": count,
        }
        for symbol, count in total_counts.items()
        if count >= 10
    ]

    # Sort results by count descending
    sorted_results = sorted(filtered_results, key=lambda x: x["count"], reverse=True)

    # Save as Pickle
    pickle_filename = MENTIONS_DIR / f"{run_id}_mentions.pkl"
    with open(pickle_filename, "wb") as f:
        pickle.dump(sorted_results, f)
    print(f"\n🎯 Results saved to: {pickle_filename}")

    # Save as CSV for inspection
    csv_filename = MENTIONS_DIR / f"{run_id}_mentions.csv"
    with open(csv_filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["symbol", "company", "count"])
        writer.writeheader()
        writer.writerows(sorted_results)

    if sorted_results:
        print(f"📊 Found symbols (>=10 mentions): {len(sorted_results)}")

        # Show top results
        print("\n🏆 Top symbols:")
        for entry in sorted_results[:10]:
            print(f"  {entry['symbol']} ({entry['company']}): {entry['count']} mentions")
    else:
        print("❌ No symbols with >=10 mentions found.")


if __name__ == "__main__":
    start_time = datetime.now()

    scan_wsb_mentions()

    end_time = datetime.now()
    duration = end_time - start_time
    print(f"\nThe script took {duration.total_seconds():.2f} seconds to run.")
