import praw
import requests
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os


def setup_reddit():
    """Initialize Reddit API connection"""
    load_dotenv("./reddit_secret.env")
    session = requests.Session()
    # session.verify = False  # Disable SSL verification (not recommended in production)
    return praw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        user_agent=os.getenv("REDDIT_USER_AGENT"),
        requestor_kwargs={"session": session},
    )


def find_symbol_matches(text, pattern):
    """Find symbol matches in text and return details about what was found"""
    matches = []
    variations = set()

    found_matches = pattern.finditer(text)

    for match in found_matches:
        matches.append(
            {
                "match": match.group(),
                "start": match.start(),
                "end": match.end(),
                "context": text[max(0, match.start() - 20) : match.end() + 20].strip(),
            }
        )
        variations.add(match.group())

    return matches, variations


def check_symbol():
    """Main function to manually check a specific symbol"""
    # Get symbol from user
    symbol = input("Enter symbol to check: ").strip().upper()
    if not symbol:
        print("No symbol entered. Exiting.")
        return

    print(f"\nSearching for '{symbol}' in r/wallstreetbets...")
    print("=" * 50)

    # Initialize
    reddit = setup_reddit()
    wsb = reddit.subreddit("wallstreetbets")
    cutoff_time = datetime.now() - timedelta(days=1)
    # Pattern for exact matches with word boundaries
    pattern = re.compile(rf"\b(\${symbol}|{symbol})\b")

    # Results tracking
    post_matches = []
    comment_matches = []
    all_variations = set()
    total_posts_found = 0
    total_comments_found = 0

    # Scan new posts (last 24h)
    print("Scanning recent posts...")

    for post in wsb.new(limit=100):
        post_time = datetime.fromtimestamp(post.created_utc)
        if post_time < cutoff_time:
            continue

        # Check post title and text
        combined_text = f"{post.title} {post.selftext}"
        post_finds, post_variations = find_symbol_matches(combined_text, pattern)

        if post_finds:
            total_posts_found += len(post_finds)
            all_variations.update(post_variations)
            post_matches.append({"post": post, "matches": post_finds, "count": len(post_finds)})

        # Check comments
        try:
            post.comments.replace_more(limit=0)
            comment_count_for_post = 0

            for comment in post.comments.list():
                comment_finds, comment_variations = find_symbol_matches(comment.body, pattern)
                if comment_finds:
                    comment_count_for_post += len(comment_finds)
                    all_variations.update(comment_variations)

            if comment_count_for_post > 0:
                total_comments_found += comment_count_for_post
                comment_matches.append({"post": post, "count": comment_count_for_post})

        except Exception as e:
            print(f"Error reading comments for post: {e}")

    # Display results
    print(f"\n🎯 RESULTS FOR '{symbol}'")
    print("=" * 50)
    print(f"📊 Total mentions in posts: {total_posts_found}")
    print(f"💬 Total mentions in comments: {total_comments_found}")
    print(f"🔍 Symbol variations found: {', '.join(sorted(all_variations)) if all_variations else 'None'}")

    # Show post matches
    if post_matches:
        print(f"\n📄 POSTS WITH MENTIONS ({len(post_matches)} posts):")
        print("-" * 50)
        for match_data in post_matches:
            post = match_data["post"]
            count = match_data["count"]
            print(f"Title: {post.title}")
            print(f"Link: https://reddit.com{post.permalink}")
            print(f"Upvotes: {post.score} | Comments: {post.num_comments} | Mentions: {count}")

            # Show context of matches
            for match in match_data["matches"]:
                print(f"  └─ Found '{match['match']}': ...{match['context']}...")
            print()

    # Show comment matches
    if comment_matches:
        print(f"\n💬 POSTS WITH COMMENT MENTIONS ({len(comment_matches)} posts):")
        print("-" * 50)
        for match_data in comment_matches:
            post = match_data["post"]
            count = match_data["count"]
            print(f"Title: {post.title}")
            print(f"Link: https://reddit.com{post.permalink}")
            print(f"Upvotes: {post.score} | Comments: {post.num_comments} | Comment mentions: {count}")
            print()

    # Summary
    if total_posts_found == 0 and total_comments_found == 0:
        print("❌ No mentions found for this symbol in the last 24 hours.")
    else:
        total_mentions = total_posts_found + total_comments_found
        unique_posts = len(set([m["post"].id for m in post_matches + comment_matches]))
        print(f"📈 SUMMARY:")
        print(f"Total mentions: {total_mentions}")
        print(f"Unique posts involved: {unique_posts}")


if __name__ == "__main__":
    check_symbol()
