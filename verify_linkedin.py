import telegram_bot
import os
from dotenv import load_dotenv

load_dotenv()

# Double check env vars
if not os.getenv("OPENROUTER_API_KEY"):
    print("WARNING: OPENROUTER_API_KEY not found in env")

url = "https://www.linkedin.com/posts/apurvjain17_aiengineering-machinelearning-applesilicon-activity-7405888512308338688-ZEe6?utm_medium=ios_app&rcm=ACoAACyRWc0Bd2fzHJWdrEgnPeHIB4wAqjyjovo&utm_source=social_share_send&utm_campaign=share_via"

print(f"Testing LinkedIn URL: {url}")

# Ensure we are using the real functions
summary = telegram_bot.scrape_and_summarize(url)

print("\n--- Summary Result ---")
if summary:
    print(summary[:500] + "..." if len(summary) > 500 else summary)
    print("\nPASS: Summary generated via Jina fallback/routing")
else:
    print("FAIL: No summary generated")
