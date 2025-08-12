
import logging
import hmac
import hashlib
import re
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(level=logging.INFO)

# ===== ADMIN SETTINGS =====
ADMIN_ID = 6148674492  # Replace with your Telegram ID
PRICE_INFO = "💳 Send 10 USDT to wallet: `your-wallet-address-here` and send /verify <transaction_id>"

# ===== STORAGE =====
approved_users = set()
user_data = {}

# --- Prediction ---
def predict_mines(server_seed: str, client_seed: str, nonce: int, mine_count: int):
    result = []
    i = 0
    while len(result) < mine_count:
        message = f"{client_seed}:{nonce}:{i}"
        hmac_hash = hmac.new(server_seed.encode(), message.encode(), hashlib.sha256).hexdigest()
        for j in range(0, len(hmac_hash), 4):
            num = int(hmac_hash[j:j+4], 16)
            pos = num % 25
            if pos not in result:
                result.append(pos)
                if len(result) == mine_count:
                    break
        i += 1
    return [(p // 5, p % 5) for p in result]

def render_board(mines: list) -> str:
    board = ""
    for i in range(5):
        for j in range(5):
            board += "💣" if (i, j) in mines else "🟩"
        board += "\n"
    return board

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    full_name = update.effective_user.full_name

    # Notify admin of new user
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"🚨 New user started the bot:\n\n"
             f"🆔 ID: `{user_id}`\n"
             f"👤 Name: {full_name}",
        parse_mode="Markdown"
    )

    if user_id not in approved_users:
        await update.message.reply_text(f"🚫 Access Denied.\n\n{PRICE_INFO}")
        return
    user_data[user_id] = {"step": "server_seed"}
    await update.message.reply_text("🔐 Please enter your **unhashed server seed**:")

async def verify_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if len(context.args) == 0:
        await update.message.reply_text("❌ Usage: /verify <transaction_id>")
        return
    txn_id = context.args[0]
    await update.message.reply_text("✅ Payment verification submitted. Please wait for admin approval.")
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"💰 Payment verification from user {user_id}\nTransaction ID: `{txn_id}`\n\nApprove: /approve {user_id}\nDeny: /deny {user_id}"
    )

async def approve_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized.")
        return
    if len(context.args) == 0:
        await update.message.reply_text("Usage: /approve <user_id>")
        return
    uid = int(context.args[0])
    approved_users.add(uid)
    await update.message.reply_text(f"✅ Approved user {uid}")
    await context.bot.send_message(chat_id=uid, text="✅ Your payment has been approved! You can now use the bot.")

async def deny_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized.")
        return
    if len(context.args) == 0:
        await update.message.reply_text("Usage: /deny <user_id>")
        return
    uid = int(context.args[0])
    if uid in approved_users:
        approved_users.remove(uid)
    await update.message.reply_text(f"❌ Denied user {uid}")
    await context.bot.send_message(chat_id=uid, text="❌ Your payment verification was denied.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in approved_users:
        await update.message.reply_text(f"🚫 Access Denied.\n\n{PRICE_INFO}")
        return

    text = update.message.text.strip()
    step = user_data.get(user_id, {}).get("step")

    if step == "server_seed":
        if not re.fullmatch(r"[0-9a-fA-F]{64}", text):
            await update.message.reply_text("❌ Invalid server seed. Must be 64-character hex.")
            return
        user_data[user_id]["server_seed"] = text
        user_data[user_id]["step"] = "client_seed"
        await update.message.reply_text("📝 Enter your **client seed**:")
        return

    if step == "client_seed":
        if not re.fullmatch(r"[a-zA-Z0-9_\-\.]{3,50}", text):
            await update.message.reply_text("❌ Invalid client seed format.")
            return
        user_data[user_id]["client_seed"] = text
        user_data[user_id]["step"] = "nonce"
        await update.message.reply_text("🔢 Enter your **nonce**:")
        return

    if step == "nonce":
        if not text.isdigit():
            await update.message.reply_text("❌ Nonce must be a number.")
            return
        user_data[user_id]["nonce"] = int(text)
        user_data[user_id]["step"] = "mine_count"
        keyboard = [[InlineKeyboardButton(f"{i} Mines", callback_data=str(i))] for i in range(1, 11)]
        await update.message.reply_text("🧮 Select number of mines:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

async def handle_mine_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if user_id not in approved_users:
        await query.edit_message_text(f"🚫 Access Denied.\n\n{PRICE_INFO}")
        return

    mine_count = int(query.data)
    server_seed = user_data[user_id]["server_seed"]
    client_seed = user_data[user_id]["client_seed"]
    nonce = user_data[user_id]["nonce"]

    mines = predict_mines(server_seed, client_seed, nonce, mine_count)
    board = render_board(mines)
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=f"🎯 Predicted Board with {mine_count} mines:\n\n{board}\n\n✅ Hit /start to run again."
    )

def main():
    TOKEN = "8223512483:AAGEEBnxiflEq_o63PXpF3pPupb3FQjEMCU"
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("verify", verify_payment))
    app.add_handler(CommandHandler("approve", approve_user))
    app.add_handler(CommandHandler("deny", deny_user))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_mine_selection))

    print("✅ Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
