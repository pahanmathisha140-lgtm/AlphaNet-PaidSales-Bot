import os
import sqlite3
from datetime import date, datetime, timedelta

from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ==========================================
# CONFIGURATION
# ==========================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

DB_NAME = "customers.db"


# ==========================================
# DATABASE
# ==========================================

def db():
    return sqlite3.connect(DB_NAME)


def setup_database():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            package TEXT NOT NULL,
            amount REAL NOT NULL,
            payment TEXT,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("PRAGMA table_info(customers)")
    columns = [row[1] for row in cur.fetchall()]

    if "payment" not in columns:
        cur.execute(
            "ALTER TABLE customers ADD COLUMN payment TEXT"
        )

    cur.execute("""
        CREATE TABLE IF NOT EXISTS periods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            report_sent INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


# ==========================================
# ADMIN CHECK
# ==========================================

def is_admin(update):
    return (
        update.effective_user is not None
        and update.effective_user.id == ADMIN_ID
    )


# ==========================================
# MAIN MENU
# ==========================================

def main_menu():
    keyboard = [
        [
            KeyboardButton("➕ Add Customer"),
            KeyboardButton("👥 View Customers"),
        ],
        [
            KeyboardButton("📊 Sales Report"),
            KeyboardButton("🗓️ Monthly Report"),
        ],
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )


# ==========================================
# START
# ==========================================

async def start(update, context):
    if not is_admin(update):
        await update.message.reply_text(
            "⛔ Access Denied!\n"
            "මෙම Bot එක Admin සඳහා පමණයි."
        )
        return

    context.user_data.clear()

    await update.message.reply_text(
        "👋 Welcome to AlphaNet Paid Sales Manager!\n\n"
        "ඔබගේ VPN Business Management Bot එකට සාදරයෙන් පිළිගනිමු.\n\n"
        "📌 Please select an option below:",
        reply_markup=main_menu()
    )


# ==========================================
# ADD CUSTOMER
# ==========================================

async def begin_add_customer(update, context):
    context.user_data.clear()
    context.user_data["awaiting_customer"] = True

    await update.message.reply_text(
        "➕ Add New Customer\n\n"
        "👤Customer ගෙ Details ටික එවන්න."
    )


async def save_customer(update, context):
    text = update.message.text.strip()

    parts = [part.strip() for part in text.split(",")]

    if len(parts) == 4:
        name, package, amount_text, payment = parts
        phone = None

    elif len(parts) == 5:
        name, phone, package, amount_text, payment = parts

    else:
        await update.message.reply_text(
            "⚠️ Invalid Details!\n"
            "කරුණාකර Customer Details නිවැරදිව නැවත එවන්න."
        )
        return

    if not name or not package or not payment:
        await update.message.reply_text(
            "⚠️ Required Details Missing!\n"
            "සියලුම අවශ්‍ය විස්තර ඇතුළත් කරන්න."
        )
        return

    try:
        amount = float(amount_text.replace(",", ""))

        if amount < 0:
            raise ValueError

    except ValueError:
        await update.message.reply_text(
            "⚠️ Invalid Amount!\n"
            "Amount එක නිවැරදිව ඇතුළත් කරන්න."
        )
        return

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO customers
        (name, phone, package, amount, payment, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        name,
        phone,
        package,
        amount,
        payment,
        date.today().isoformat()
    ))

    customer_id = cur.lastrowid

    conn.commit()
    conn.close()

    context.user_data.clear()

    await update.message.reply_text(
        "✅ Customer Added Successfully!\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🆔 Customer ID: {customer_id}\n"
        f"👤 Name: {name}\n"
        f"📦 Package: {package}\n"
        f"💰 Amount: Rs. {amount:,.2f}\n"
        f"💳 Payment: {payment}\n"
        f"📅 Date: {date.today().isoformat()}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🎉 Customer record saved successfully!",
        reply_markup=main_menu()
    )


# ==========================================
# VIEW CUSTOMERS
# ==========================================

async def view_customers(update, context):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, name, phone, package, amount, payment, created_at
        FROM customers
        ORDER BY id DESC
    """)

    rows = cur.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text(
            "📭 No Customers Found!\n\n"
            "තවමත් Customer Records ඇතුළත් කර නැහැ.",
            reply_markup=main_menu()
        )
        return

    await update.message.reply_text(
        f"👥 Customer Directory\n"
        f"Total Customers: {len(rows)}\n"
        "━━━━━━━━━━━━━━━━━━"
    )

    for row in rows:
        cid, name, phone, package, amount, payment, created = row

        message = (
            f"🆔 Customer ID: {cid}\n"
            f"👤 Name: {name}\n"
            f"📞 Phone: {phone or 'Not Provided'}\n"
            f"📦 Package: {package}\n"
            f"💰 Amount: Rs. {amount:,.2f}\n"
            f"💳 Payment: {payment or 'Not Provided'}\n"
            f"📅 Date: {created}\n"
            "━━━━━━━━━━━━━━━━━━"
        )

        await update.message.reply_text(message)


# ==========================================
# SALES REPORT - DATE SELECTION
# ==========================================

async def sales_report(update, context):
    context.user_data.clear()
    context.user_data["awaiting_sales_date"] = True

    await update.message.reply_text(
        "📊 Sales Report\n\n"
        "📅 Sales Report ලබාගැනීමට අවශ්‍ය Date එක එවන්න.\n\n"
        "Format: YYYY-MM-DD\n"
        "Example: 2026-11-01"
    )


async def sales_report_for_date(update, context):
    text = update.message.text.strip()

    try:
        selected_date = datetime.strptime(
            text, "%Y-%m-%d"
        ).date()

        if selected_date > date.today():
            await update.message.reply_text(
                "⚠️ Future Date එකක් තෝරන්න බැහැ.\n"
                "කරුණාකර වෙනත් Date එකක් එවන්න."
            )
            return

    except ValueError:
        await update.message.reply_text(
            "⚠️ Invalid Date Format!\n\n"
            "කරුණාකර YYYY-MM-DD Format එකෙන් එවන්න.\n"
            "Example: 2026-11-01"
        )
        return

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(amount), 0)
        FROM customers
        WHERE created_at = ?
    """, (selected_date.isoformat(),))

    count, total = cur.fetchone()
    conn.close()

    context.user_data.clear()

    await update.message.reply_text(
        "📊 Daily Sales Report\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📅 Date: {selected_date.isoformat()}\n"
        f"👥 Total Customers: {count}\n"
        f"💰 Total Sales: Rs. {total:,.2f}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "✅ Report Generated Successfully!",
        reply_markup=main_menu()
    )


# ==========================================
# SET VPS PURCHASE DATE
# ==========================================

async def set_period(update, context):
    if not is_admin(update):
        return

    if not context.args:
        await update.message.reply_text(
            "⚙️ Monthly Period Setup\n\n"
            "VPS එක මිලදී ගත් දිනය ඇතුළත් කරන්න.\n\n"
            "Example:\n"
            "/setperiod 2026-11-01"
        )
        return

    try:
        start = datetime.strptime(
            context.args[0], "%Y-%m-%d"
        ).date()

    except ValueError:
        await update.message.reply_text(
            "⚠️ Invalid Date!\n"
            "YYYY-MM-DD Format එක භාවිතා කරන්න."
        )
        return

    end = start + timedelta(days=30)

    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM periods")
    exists = cur.fetchone()[0]

    if exists:
        conn.close()

        await update.message.reply_text(
            "⚠️ Monthly Period Already Exists!\n"
            "Period එක දැනටමත් Setup කරලා තියෙනවා."
        )
        return

    cur.execute("""
        INSERT INTO periods
        (start_date, end_date, report_sent)
        VALUES (?, ?, 0)
    """, (start.isoformat(), end.isoformat()))

    conn.commit()
    conn.close()

    await update.message.reply_text(
        "✅ Monthly Period Setup Completed!\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📅 Start Date: {start}\n"
        f"📅 End Date: {end}\n"
        "⏳ Duration: 30 Days\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🔔 Automatic Monthly Report Enabled!"
    )


# ==========================================
# MONTHLY REPORT
# ==========================================

async def monthly_report(update, context):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT start_date, end_date
        FROM periods
        ORDER BY id DESC
        LIMIT 1
    """)

    period = cur.fetchone()

    if not period:
        conn.close()

        await update.message.reply_text(
            "⚠️ Monthly Period Not Setup!\n\n"
            "VPS Purchase Date එක Setup කරන්න:\n"
            "/setperiod YYYY-MM-DD"
        )
        return

    start, end = period

    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(amount), 0)
        FROM customers
        WHERE created_at >= ? AND created_at < ?
    """, (start, end))

    count, total = cur.fetchone()
    conn.close()

    await update.message.reply_text(
        "🗓️ Monthly Sales Report\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📅 Period: {start} to {end}\n"
        f"👥 Total Customers: {count}\n"
        f"💰 Total Sales: Rs. {total:,.2f}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "✅ Monthly Report Generated!"
    )


# ==========================================
# AUTOMATIC MONTHLY REPORT
# ==========================================

async def automatic_report(context):
    today = date.today()

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, start_date, end_date
        FROM periods
        WHERE report_sent = 0 AND end_date <= ?
        ORDER BY id ASC
        LIMIT 1
    """, (today.isoformat(),))

    period = cur.fetchone()

    if not period:
        conn.close()
        return

    period_id, start, end = period

    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(amount), 0)
        FROM customers
        WHERE created_at >= ? AND created_at < ?
    """, (start, end))

    count, total = cur.fetchone()

    next_start = date.fromisoformat(end)
    next_end = next_start + timedelta(days=30)

    cur.execute("""
        SELECT COUNT(*) FROM periods
        WHERE start_date = ?
    """, (next_start.isoformat(),))

    if cur.fetchone()[0] == 0:
        cur.execute("""
            INSERT INTO periods
            (start_date, end_date, report_sent)
            VALUES (?, ?, 0)
        """, (next_start.isoformat(), next_end.isoformat()))

    # Mark report as sent
    cur.execute("""
        UPDATE periods
        SET report_sent = 1
        WHERE id = ?
    """, (period_id,))

    conn.commit()
    conn.close()

    message = (
        "🔔 Automatic Monthly Sales Report\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📅 Period: {start} to {end}\n"
        f"👥 Total Customers: {count}\n"
        f"💰 Total Sales: Rs. {total:,.2f}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "✅ Monthly Report Completed!"
    )

    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=message
        )

    except Exception as error:
        print("Report sending error:", error)


# ==========================================
# MESSAGE HANDLER
# ==========================================

async def handle_message(update, context):
    if not is_admin(update):
        return

    text = update.message.text.strip()

    # Main menu buttons
    menu_buttons = [
        "➕ Add Customer",
        "👥 View Customers",
        "📊 Sales Report",
        "🗓️ Monthly Report",
    ]

    # If a menu button is pressed, cancel any pending input
    if text in menu_buttons:
        context.user_data.clear()

        if text == "➕ Add Customer":
            await begin_add_customer(update, context)

        elif text == "👥 View Customers":
            await view_customers(update, context)

        elif text == "📊 Sales Report":
            await sales_report(update, context)

        elif text == "🗓️ Monthly Report":
            await monthly_report(update, context)

        return

    # Waiting for customer details
    if context.user_data.get("awaiting_customer"):
        await save_customer(update, context)
        return

    # Waiting for sales report date
    if context.user_data.get("awaiting_sales_date"):
        await sales_report_for_date(update, context)
        return


# ==========================================
# MAIN
# ==========================================

def main():
    if not BOT_TOKEN or ADMIN_ID == 0:
        print("❌ Check BOT_TOKEN and ADMIN_ID in .env")
        return

    setup_database()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setperiod", set_period))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    app.job_queue.run_repeating(
        automatic_report,
        interval=60,
        first=10
    )

    print("AlphaNet Paid Sales Manager is running...")

    app.run_polling()


if __name__ == "__main__":
    main()