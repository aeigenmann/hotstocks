"""
Hotstocks Reports Generator (Gemini)

Scans ./results/hotstocks-posts/ for files named
    [yyyymmdd-hhmm]_[TICKER]-posts.pkl

1) Identifies the *latest* timestamp prefix (yyyymmdd-hhmm).
2) Processes ALL files that share that prefix.
3) For each file, sends a structured prompt to Google Gemini to analyze
   sentiment (bullish/bearish/neutral) in the provided posts/comments.
4) Writes an HTML report for each ticker under:
       ./results/hotstocks-reports/[yyyymmdd-hhmm]_[TICKER]-report.html
   with a clean, reader-friendly layout.
5) (Re)builds an overview index page that links to all existing reports,
   grouped by their date prefix.
"""

import os
import re
import pickle
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from html import escape
import markdown


# === CONFIG ===
HOTSTOCKS_DIR = Path("./results/hotstocks/")
POSTS_DIR = Path("./results/hotstocks-posts/")
REPORTS_DIR = Path("./results/hotstocks-reports/")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
INDEX_FILE = REPORTS_DIR / "index.html"

load_dotenv("./gem_secret.env")
genai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


# === FUNCTIONS ===
def get_latest_hotstocks_prefix():
    files = HOTSTOCKS_DIR.glob("*_hotstocks.pkl")
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


def find_posts_files(prefix):
    print(f"\nSearching for posts files with prefix {prefix}...")
    files = sorted(POSTS_DIR.glob(f"{prefix}_*-posts.pkl"), key=os.path.getmtime, reverse=True)
    if not files:
        print(f"No hotstocks posts files found in {POSTS_DIR}")
        return []
    print(f"Found posts files. Processing {len(files)} files.")
    return files


def load_post_data(file_path):
    print(f"\nLoading data from {file_path}...")
    with open(file_path, "rb") as f:
        return pickle.load(f)


def markdown_to_html(text):
    # Converts Markdown text to HTML.
    return markdown.markdown(text)


def analyze_with_gemini(data, posts_text):
    print(f"Sending prompt to Gemini for analysis of {data['symbol']}...")
    prompt = f"""Du bist ein Börsenexperte. Bitte analysiere die Post-Inhalte und Kommentare darauf, ob die User dem Unternehmen {data['symbol']} ({data['company']}) bullish oder bearish gegenüberstehen.
Formatiere die Antwort in Markdown mit den folgenden Abschnitten:
**Gesamteinschätzung**: Bullish/Bearish/Neutral
**Begründung**: Warum diese Einschätzung? Liste hier idealerweise bis zu drei Kommentare mit vielen Upvotes auf, die deine Einschätzung unterstützen.
**Wichtige Punkte**: Liste hier die 3 wichtigsten Argumente auf.
**Stimmungswert**: Bewertung von -10 (sehr bearish) bis +10 (sehr bullish)

Posts:
{posts_text}
"""
    response = genai_client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    print(f"Analysis for {data['symbol']} received.")
    return markdown_to_html(response.text)


def sentiment_color(value):
    if value > 1:
        return "#4caf50"  # green
    elif value < -1:
        return "#f44336"  # red
    return "#ffc107"  # yellow


def extract_sentiment_value(text):
    match = re.search(r"Stimmungswert[^-\d]*(-?\d+)", text)
    return int(match.group(1)) if match else 0


def generate_report_html(data, analysis_html):
    print(f"Generating report for {data['symbol']}...")
    sentiment_value = extract_sentiment_value(analysis_html)
    sentiment_col = sentiment_color(sentiment_value)

    # Sort posts by upvotes desc
    sorted_posts = sorted(data["posts"], key=lambda p: p.get("upvotes", 0), reverse=True)

    post_rows = ""
    for post in sorted_posts:
        post_rows += f"""
        <tr>
            <td>{escape(post['title'])}</td>
            <td>{post['upvotes']}</td>
            <td>{len(post.get('comments', []))}</td>
            <td><a href="{post['url']}" target="_blank">Link</a></td>
        </tr>
        """

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<title>Stock Report - {data['symbol']}</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body {{ font-family: Arial, sans-serif; margin: 20px; background: #f8f9fa; }}
h1, h2 {{ color: #333; }}
.card {{ background: white; padding: 20px; margin-bottom: 20px; border-radius: 8px;
         box-shadow: 0 2px 6px rgba(0,0,0,0.1); }}
.sentiment-bar {{ height: 20px; background: #ddd; border-radius: 10px; overflow: hidden; }}
.sentiment-fill {{ height: 100%; width: {(sentiment_value + 10) / 20 * 100}%; background: {sentiment_col}; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
th {{ background: #eee; }}
@media (max-width: 600px) {{
    table, thead, tbody, th, td, tr {{ display: block; }}
    tr {{ margin-bottom: 10px; }}
    td {{ border: none; }}
}}
</style>
</head>
<body>
<h1>Stock Report - {data['symbol']} ({data['company']})</h1>

<div class="card">
<h2>Analyse</h2>
<div>{analysis_html}</div>
<div class="sentiment-bar">
  <div class="sentiment-fill"></div>
</div>
</div>

<div class="card">
<h2>Posts</h2>
<table>
<thead>
<tr><th>Titel</th><th>Upvotes</th><th>Kommentare</th><th>URL</th></tr>
</thead>
<tbody>
{post_rows}
</tbody>
</table>
</div>

</body>
</html>
"""


def save_report(file_prefix, symbol, html_content):
    file_path = REPORTS_DIR / f"{file_prefix}_{symbol}-report.html"
    print(f"Saving report for {symbol} to {file_path}...")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    return file_path


def generate_index():
    print("Generating index page...")
    report_files = sorted(REPORTS_DIR.glob("*-report.html"), key=os.path.getmtime, reverse=True)
    reports_by_date = {}
    for f in report_files:
        date_prefix = f.name.split("_")[0]
        reports_by_date.setdefault(date_prefix, []).append(f)

    index_html = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<title>Hot Stocks</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body { font-family: Arial, sans-serif; margin: 20px; background: #f8f9fa; }
h1 { color: #333; }
.card { background: white; padding: 20px; margin-bottom: 20px; border-radius: 8px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.1); }
</style>
</head>
<body>
<h1>Hot Stocks</h1>
"""

    for date, files in reports_by_date.items():
        date_str = datetime.strptime(date, "%Y%m%d-%H%M").strftime("%Y-%m-%d %H:%M")
        index_html += f"<div class='card'><h2>{date_str}</h2><ul>"
        for f in files:
            sym = f.name.split("_")[1].replace("-report.html", "")
            index_html += f"<li><a href='{f.name}'>{sym}</a></li>"
        index_html += "</ul></div>"

    index_html += "</body></html>"

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(index_html)
    print(f"Index page generated at {INDEX_FILE}.")


def main():
    print("Finding latest hotstocks file...")
    latest_prefix = get_latest_hotstocks_prefix()
    if not latest_prefix:
        print(f"No hotstocks file found in {HOTSTOCKS_DIR}")
        return
    print(f"Latest prefix found: {latest_prefix}")

    files = find_posts_files(latest_prefix)

    for file in files:
        data = load_post_data(file)

        posts_text = ""
        for p in data["posts"]:
            # Start with the main post details
            posts_text += (
                f"Title: {p['title']}\n" f"Content: {p.get('content','')}\n" f"Upvotes: {p.get('upvotes',0)}\n"
            )
            # Add a section for comments if they exist
            comments = p.get("comments", [])
            if comments:
                posts_text += "Comments:\n"
                for comment in comments:
                    posts_text += (
                        f"  - Comment Body: {comment.get('body','')}\n"
                        f"  - Comment Upvotes: {comment.get('upvotes',0)}\n"
                        f"  - Comment ID: {comment.get('id','')}\n"
                        f"  - Comment Parent ID: {comment.get('parent_id','')}\n\n"
                    )
            posts_text += "\n\n"  # Separate each post clearly

        analysis_html = analyze_with_gemini(data, posts_text)
        html_report = generate_report_html(data, analysis_html)
        save_report(latest_prefix, data["symbol"], html_report)

    generate_index()
    print("\nAll reports generated successfully!")


if __name__ == "__main__":
    main()
