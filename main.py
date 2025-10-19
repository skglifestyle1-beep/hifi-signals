import os, logging, datetime as dt
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from models import Session, Signal
from strategy import daily_bias, key_levels,
Copy
Share
confirm
from market_data import usd_size
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
log = logging.getLogger(name)
TOKEN   = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT')
CAPITAL = float(os.getenv('CAPITAL_USD', 1000))
SUPPORT, RESIST = [], []
BIAS = 'NONE'
bot = None   # set later
---------- commands ----------
async def start(update: Update, _):
await update.message.reply_text("🟢 HIFI Signal Bot (manual trade)\n"
"/levels – key levels\n/status – last signal\n/capital – set account size")
async def levels(update: Update, _):
txt = f"Daily bias: {BIAS}\nSupports: {', '.join(f'{s:.4f}' for s in SUPPORT)}\n" 
f"Resist: {', '.join(f'{r:.4f}' for r in RESIST)}"
await update.message.reply_text(txt)
async def status(update: Update, _):
with Session() as s:
last = s.query(Signal).order_by(Signal.ts.desc()).first()
if not last:
await update.message.reply_text("No signals yet.")
else:
await update.message.reply_text(f"{'🟢' if last.side=='LONG' else '🔴'} {last.side}  E{last.entry}  SL{last.sl}  TP{last.tp}")
async def capital(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
try:
global CAPITAL
CAPITAL = float(ctx.args[0])
await update.message.reply_text(f"Capital set to {CAPITAL} USDT")
except:
await update.message.reply_text("Usage: /capital 1250")
---------- jobs ----------
async def daily_job():
global SUPPORT, RESIST, BIAS
BIAS = daily_bias()
SUPPORT, RESIST = key_levels()
await bot.send_message(chat_id=CHAT_ID, text="🔁 Levels updated (13-18 UTC window)")
await levels(Update(update_id=0, message=None), None)
async def scan_job():
for lvl in SUPPORT:
sig = confirm('LONG', lvl)
if sig and BIAS == 'LONG':
await send_alert(sig)
for lvl in RESIST:
sig = confirm('SHORT',lvl)
if sig and BIAS == 'SHORT':
await send_alert(sig)
async def send_alert(sig):
sz = usd_size(abs(sig['entry']-sig['sl']), CAPITAL)
txt = (f"{'🟢' if sig['side']=='LONG' else '🔴'} HIFI {sig['side']} SET-UP\n"
f"Level: {sig['level']:.4f}\nEntry: {sig['entry']:.4f}\n"
f"SL: {sig['sl']:.4f}\nTP: {sig['tp']:.4f}\nRR: 1:{sig['rr']:.1f}\n"
f"Suggested size: {sz} USDT (1 % risk)\n⚠️ MANUAL TRADE ONLY")
await bot.send_message(chat_id=CHAT_ID, text=txt)
with Session() as s:
s.add(Signal(side=sig['side'], level=sig['level'], entry=sig['entry'],
sl=sig['sl'], tp=sig['tp'], rr=sig['rr']))
s.commit()
---------- run ----------
def main():
global bot
app = Application.builder().token(TOKEN).build()
bot = app.bot
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("levels", levels))
app.add_handler(CommandHandler("status", status))
app.add_handler(CommandHandler("capital", capital))
Copy
sched = AsyncIOScheduler(timezone="UTC")
sched.add_job(daily_job, 'cron', hour=0, minute=5)
sched.add_job(scan_job, 'cron', minute='*/15')
sched.start()

app.run_polling()
if name == "main":
main()
