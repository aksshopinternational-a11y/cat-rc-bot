import os, json, asyncio
import google.generativeai as genai
from tavily import TavilyClient
from newspaper import Article
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Read from Render Environment
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_KEY")
TAVILY_KEY = os.environ.get("TAVILY_KEY")

print(f"Checking keys: Telegram exists? {bool(TELEGRAM_TOKEN)} | Gemini exists? {bool(GEMINI_KEY)} | Tavily exists? {bool(TAVILY_KEY)}")

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')
tavily = TavilyClient(api_key=TAVILY_KEY)

user_current_rc = {}

def fetch_article(url):
    try:
        a = Article(url)
        a.download()
        a.parse()
        return a.text
    except Exception as e:
        print(f"Fetch error: {e}")
        return ""

def get_rc(topic):
    print(f"Searching for {topic}...")
    query = f"{topic} longform essay site:aeon.co/essays OR site:nautil.us OR site:theatlantic.com"
    search = tavily.search(query=query, search_depth="advanced", max_results=5)
    for res in search['results'][:3]:
        url = res['url']
        text = fetch_article(url)
        print(f"Trying {url} length {len(text)}")
        if len(text) < 2000: 
            continue
        prompt = f"""You are CAT RC setter. From article create CAT RC set.
        Article: {text[:4000]}
        URL: {url}
        Return ONLY valid JSON: {{"passage": "500-550 words argumentative CAT level", "source": "{url}", "questions": [{{"no":1,"type":"Main Idea","question":"...","options":{{"A":"...","B":"...","C":"...","D":"..."}},"answer":"B","explanation":"..."}},{{"no":2,"type":"Inference","question":"...","options":{{"A":"...","B":"...","C":"...","D":"..."}},"answer":"C","explanation":"..."}},{{"no":3,"type":"Tone","question":"...","options":{{"A":"...","B":"...","C":"...","D":"..."}},"answer":"A","explanation":"..."}},{{"no":4,"type":"Application","question":"...","options":{{"A":"...","B":"...","C":"...","D":"..."}},"answer":"D","explanation":"..."}}]}}"""
        try:
            resp = model.generate_content(prompt)
            j = resp.text.replace("```json","").replace("```","").strip()
            data = json.loads(j)
            print("RC Generated OK")
            return data
        except Exception as e:
            print(f"LLM error: {e}")
            continue
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 CAT RC Live Bot - 100% Web\n\nCommands:\n/rc philosophy - Aeon philosophy\n/rc science\n/rc psychology\n/rc technology\n/rc - random\n\nThen reply: 1B 2C 3A 4D")

async def rc_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = " ".join(context.args) if context.args else "philosophy"
    await update.message.reply_text(f"🔍 Searching best '{topic}' article from Aeon/Atlantic...\nThis takes 15-20 sec...")
    data = get_rc(topic)
    if not data:
        await update.message.reply_text("❌ Could not fetch. Try /rc again.")
        return
    user_current_rc[update.effective_user.id] = data
    msg = f"📖 PASSAGE\nSource: {data['source']}\n\n{data['passage']}\n\n--- QUESTIONS ---\n"
    for q in data['questions']:
        msg += f"\nQ{q['no']} ({q['type']}): {q['question']}\n"
        for k,v in q['options'].items(): 
            msg += f"{k}: {v}\n"
    msg += "\nReply like: 1B 2C 3A 4D"
    for i in range(0, len(msg), 4000):
        await update.message.reply_text(msg[i:i+4000])

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if not any(x in txt for x in ["1A","1B","1C","1D","2A","2B","2C"]): 
        return
    data = user_current_rc.get(update.effective_user.id)
    if not data:
        await update.message.reply_text("First do /rc")
        return
    user_ans = {}
    for p in txt.replace(","," ").split():
        if len(p)>=2 and p[0] in "1234" and p[1] in "ABCDabcd":
            user_ans[int(p[0])] = p[1].upper()
    score=0
    reply="📊 Result:\n\n"
    for q in data['questions']:
        no=q['no']; corr=q['answer']; u=user_ans.get(no,"?"); 
        if u==corr: score+=1
        reply+=f"Q{no}: You {u} | Correct {corr} {'✅' if u==corr else '❌'}\n"
        if u!=corr: reply+=f"   Why: {q['explanation']}\n\n"
    reply+=f"\nScore: {score}/4\n"
    await update.message.reply_text(reply)

# Main
async def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("rc", rc_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check))
    print("🚀 Bot is Live - Go to Telegram /start")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
