import telebot
import requests
from bs4 import BeautifulSoup
import trafilatura
import json
import re

# Telegram Bot Token
BOT_TOKEN = "8747303635:AAE4Ma1V3opCg_FkVpwtwn1PMlbmFmKRF7E"

# আপনার রিকোয়ারমেন্ট অনুযায়ী 'posts' নোড
FIREBASE_DB_URL = "https://golpo-910cc-default-rtdb.firebaseio.com/posts.json"

bot = telebot.TeleBot(BOT_TOKEN)

# URL ভ্যালিডেশন চেক
def is_valid_url(url):
    regex = re.compile(
        r'^(?:http|ftp)s?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return re.match(regex, url) is not None

# ওয়েবসাইট থেকে হেডিং এবং গল্প স্ক্র্যাপ করার ফাংশন
def scrape_story(url):
    try:
        # মেথড ১: Trafilatura দিয়ে স্মার্ট এক্সট্রাকশন
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            extracted_json = trafilatura.extract(downloaded, output_format='json', include_comments=False)
            if extracted_json:
                data = json.loads(extracted_json)
                heading = data.get('title')
                details = data.get('text')
                if heading and details and len(details) > 80:
                    return heading.strip(), details.strip()

        # মেথড ২: BeautifulSoup দিয়ে ফলব্যাক এক্সট্রাকশন
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # হেডিং খোঁজা
        heading_tag = soup.find('h1') or soup.find('title')
        heading = heading_tag.get_text(strip=True) if heading_tag else "অজানা গল্প"

        # গল্পের বডি (details) খোঁজা
        paragraphs = soup.find_all('p')
        details_list = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 25]
        details = "\n\n".join(details_list)

        if details:
            return heading, details
        return None, None

    except Exception as e:
        print(f"Scraping Error: {e}")
        return None, None

# Firebase Database-এ আপলোড করার ফাংশন (শুধু heading এবং details)
def upload_to_firebase(heading, details):
    try:
        payload = {
            "heading": heading,
            "details": details
        }
        
        response = requests.post(FIREBASE_DB_URL, json=payload, timeout=10)
        
        if response.status_code == 200:
            return True, response.json().get('name')
        else:
            return False, response.text
    except Exception as e:
        return False, str(e)

# Start কমান্ড
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "👋 স্বাগতম! গল্পের লিংক পাঠান, আমি সেটি FireBase আপলোড করে দেব।")

# লিংক হ্যান্ডলার
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    url = message.text.strip()

    if not is_valid_url(url):
        bot.reply_to(message, "❌ অনুগ্রহ করে একটি সঠিক ওয়েবসাইটের URL/Link পাঠান!")
        return

    status_msg = bot.reply_to(message, "⏳ লিংক থেকে গল্প স্ক্র্যাপ করা হচ্ছে...")

    heading, details = scrape_story(url)

    if not heading or not details:
        bot.edit_message_text("❌ দুঃখিত! এই লিংকটি থেকে গল্প সংগ্রহ করা সম্ভব হয়নি।", 
                              chat_id=message.chat.id, 
                              message_id=status_msg.message_id)
        return

    bot.edit_message_text(f"📖 গল্প পাওয়া গেছে!\n\n**Heading:** {heading}\n\nFirebase 'posts'-এ আপলোড করা হচ্ছে...", 
                          chat_id=message.chat.id, 
                          message_id=status_msg.message_id,
                          parse_mode="Markdown")

    # Firebase-এ ডাটা আপলোড
    success, db_id = upload_to_firebase(heading, details)

    if success:
        preview = details[:200] + "..." if len(details) > 200 else details
        final_text = (
            f"✅ **সফলভাবে `posts` নোডে সেভ হয়েছে!**\n\n"
            f"📌 **Heading:** {heading}\n"
            f"🔑 **Post ID:** `{db_id}`\n\n"
            f"📝 **Details Preview:**\n{preview}"
        )
        bot.send_message(message.chat.id, final_text, parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, f"❌ Firebase Error:\n`{db_id}`", parse_mode="Markdown")

if __name__ == "__main__":
    print("🤖 Bot is running...")
    bot.infinity_polling()