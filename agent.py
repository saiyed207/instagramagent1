import os
import json
import re
import requests

# --- Configuration & Environment Variables ---
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
IG_USER_ID = os.environ.get("IG_USER_ID")
INPUT_POST_URL = os.environ.get("INPUT_POST_URL", "").strip()
INPUT_KEYWORD = os.environ.get("INPUT_KEYWORD", "").strip()
INPUT_REPLY = os.environ.get("INPUT_REPLY", "").strip()

GRAPH_URL = "https://graph.facebook.com/v19.0"

# --- Helper Functions ---
def load_json(filename, default):
    """Loads JSON data from a file, returns default if not found."""
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return default
    return default

def save_json(filename, data):
    """Saves data to a JSON file."""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def extract_shortcode(url):
    """Extracts Instagram shortcode from /p/ or /reel/ URL."""
    match = re.search(r"instagram\.com/(?:p|reel)/([^/?#&]+)", url)
    return match.group(1) if match else None

# --- Main Logic ---
def main():
    if not ACCESS_TOKEN or not IG_USER_ID:
        print("❌ ERROR: ACCESS_TOKEN or IG_USER_ID missing from environment variables.")
        return

    print("🚀 Starting Instagram Auto-Reply Agent...")
    
    # Load state databases
    rules = load_json("rules.json", {})
    processed = load_json("processed_comments.json", [])

    # 1. Process new rules from GitHub Actions inputs
    if INPUT_POST_URL and INPUT_KEYWORD and INPUT_REPLY:
        shortcode = extract_shortcode(INPUT_POST_URL)
        if shortcode:
            rules[shortcode] = {
                "keyword": INPUT_KEYWORD.lower(),
                "reply": INPUT_REPLY
            }
            save_json("rules.json", rules)
            print(f"✅ Added new rule for shortcode '{shortcode}': '{INPUT_KEYWORD}' -> '{INPUT_REPLY}'")
        else:
            print(f"⚠️ Could not extract shortcode from provided URL: {INPUT_POST_URL}")

    if not rules:
        print("⚠️ No rules configured. Exiting.")
        return

    # 2. Fetch the 50 most recent media items
    print("🔄 Fetching recent media items...")
    media_url = f"{GRAPH_URL}/{IG_USER_ID}/media"
    media_params = {
        "fields": "id,shortcode",
        "limit": 50,
        "access_token": ACCESS_TOKEN
    }
    
    media_res = requests.get(media_url, params=media_params).json()
    if "error" in media_res:
        print(f"❌ Error fetching media: {media_res['error'].get('message')}")
        return

    media_items = media_res.get("data", [])
    print(f"✅ Retrieved {len(media_items)} media items.")

    # 3. Process comments for media matching our rules
    for item in media_items:
        shortcode = item.get("shortcode")
        media_id = item.get("id")

        if shortcode in rules:
            rule = rules[shortcode]
            keyword = rule["keyword"]
            reply_text = rule["reply"]

            print(f"\n📝 Checking comments for media '{shortcode}' (ID: {media_id})...")
            
            # Fetch comments for this media item
            comments_url = f"{GRAPH_URL}/{media_id}/comments"
            comments_params = {"access_token": ACCESS_TOKEN}
            comments_res = requests.get(comments_url, params=comments_params).json()
            
            if "error" in comments_res:
                print(f"⚠️ Error fetching comments for {shortcode}: {comments_res['error'].get('message')}")
                continue

            comments = comments_res.get("data", [])
            
            for comment in comments:
                c_id = comment.get("id")
                c_text = comment.get("text", "").lower()

                # Check if keyword is in comment AND we haven't replied yet
                if keyword in c_text and c_id not in processed:
                    print(f"💬 Keyword '{keyword}' found in comment {c_id}. Replying...")
                    
                    # Post the reply
                    reply_url = f"{GRAPH_URL}/{c_id}/replies"
                    reply_data = {
                        "message": reply_text,
                        "access_token": ACCESS_TOKEN
                    }
                    reply_res = requests.post(reply_url, data=reply_data).json()

                    if "id" in reply_res:
                        print(f"✅ Successfully replied to comment {c_id}!")
                        processed.append(c_id)
                    else:
                        print(f"❌ Failed to reply to {c_id}: {reply_res.get('error', {}).get('message')}")
    
    # 4. Save updated processed comments back to database
    save_json("processed_comments.json", processed)
    print("\n🏁 Processing complete. State saved.")

if __name__ == "__main__":
    main()
