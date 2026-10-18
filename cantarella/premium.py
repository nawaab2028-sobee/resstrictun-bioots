from pyrogram import Client, filters, enums
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from database.db import db
from config import OWNER_ID
from datetime import date, datetime, timedelta, timezone, time as dtime
from logger import LOGGER

logger = LOGGER(__name__)

IST = timezone(timedelta(hours=5, minutes=30))


def _to_ist(value):
    """
    Converts a stored expiry/start value to an aware datetime in Indian Standard Time.
      - naive datetimes were saved with datetime.now() (server clock) -> server tz is attached first
      - a date / "YYYY-MM-DD" string (from /add_premium) means: valid till the END of that day (IST)
    Returns None if the value is empty or unreadable.
    """
    if value is None or value == "":
        return None
    try:
        if isinstance(value, str):
            value = value.strip()
            if len(value) == 10:
                value = date.fromisoformat(value)       # "YYYY-MM-DD" (date only)
            else:
                value = datetime.fromisoformat(value)
        if isinstance(value, date) and not isinstance(value, datetime):
            return datetime.combine(value, dtime(23, 59)).replace(tzinfo=IST)
        if value.tzinfo is None:
            value = value.replace(tzinfo=datetime.now().astimezone().tzinfo)
        return value.astimezone(IST)
    except Exception:
        return None


def _fmt_ist(dt):
    return dt.strftime("%d %b %Y, %I:%M %p") + " IST"


def _fmt_left(delta):
    secs = max(0, int(delta.total_seconds()))
    days, rem = divmod(secs, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    return f"{days}d {hours}h {minutes}m"


def _active_grants(user_id, user_data):
    """
    Returns (grants, expired_premium_dt).
    grants = list of dicts {label, start_dt, end_dt} for every ACTIVE unlimited-access grant
    (owner, premium, owner-granted auth). end_dt None = permanent.
    """
    now = datetime.now(IST)
    grants = []
    expired_premium = None

    if user_id == OWNER_ID:
        grants.append({"label": "Owner", "start": None, "end": None})

    if user_data.get("is_auth"):
        end = _to_ist(user_data.get("auth_expiry"))
        if user_data.get("auth_expiry") is None or (end and end > now):
            grants.append({"label": "Premium", "start": _to_ist(user_data.get("auth_start")), "end": end})

    if user_data.get("is_premium"):
        end = _to_ist(user_data.get("premium_expiry"))
        if user_data.get("premium_expiry") in (None, "") or (end and end > now):
            grants.append({"label": "Premium", "start": _to_ist(user_data.get("premium_start")), "end": end})
        elif end:
            expired_premium = end

    return grants, expired_premium

# ======================================================
# USER COMMANDS - Professional & Informative
# ======================================================

# /myplan - Detailed Plan & Quota Overview
@Client.on_message(filters.command("myplan") & filters.private)
async def my_plan(client: Client, message: Message, user=None):
    # `user` is passed by the "Back to My Plan" button (there message.from_user is the bot itself)
    user = user or message.from_user
    user_id = user.id

    # 1. Ensure User Exists (Fixing the 'ensure_user' error manually)
    if not await db.is_user_exist(user_id):
        await db.add_user(user_id, user.first_name)

    # 2. Fetch User Data Directly from DB
    user_data = await db.col.find_one({'id': user_id}) or {}

    daily_usage = user_data.get('daily_usage', 0)
    # Note: total_saves needs to be tracked in your traffic logic to show up here
    total_saves = user_data.get('total_saves', 0)

    # 3. Generate Status Text (owner / premium / owner-granted auth all count as Premium)
    grants, expired_premium = _active_grants(user_id, user_data)

    if grants:
        # show the grant that lasts the longest (permanent beats everything)
        grant = max(grants, key=lambda g: (g["end"] is None, g["end"] or datetime.min.replace(tzinfo=IST)))
        now_ist = datetime.now(IST)

        if grant["label"] == "Owner":
            period_text = "<b>📅 Validity:</b> <code>Lifetime (Owner)</code>\n\n"
        else:
            start_text = _fmt_ist(grant["start"]) if grant["start"] else "Not recorded"
            if grant["end"] is None:
                end_text = "Lifetime (Permanent)"
                left_text = ""
            else:
                end_text = _fmt_ist(grant["end"])
                left_text = f"<b>⌛ Time Left:</b> <code>{_fmt_left(grant['end'] - now_ist)}</code>\n"
            period_text = (
                f"<b>🟢 Activated From:</b> <code>{start_text}</code>\n"
                f"<b>📅 Valid Till:</b> <code>{end_text}</code>\n"
                f"{left_text}\n"
            )

        plan_text = (
            f"<b>👑 Premium Status: Active</b>\n\n"
            f"{period_text}"
            f"<b>♾️ Daily Tokens:</b> Unlimited\n"
            f"<b>♾️ Batch Limit:</b> Unlimited\n"
            f"<b>📊 Total Lifetime Saves:</b> <code>{total_saves}</code>\n\n"
            "<i>Thank you for supporting the bot! 🎉</i>"
        )
    else:
        # Free Logic
        daily_limit = 5
        tokens_left = max(0, daily_limit - daily_usage)
        expired_text = (
            f"<b>⚠️ Your premium expired on:</b> <code>{_fmt_ist(expired_premium)}</code>\n\n"
            if expired_premium else ""
        )

        plan_text = (
            f"<b>👤 Plan: Free Tier</b>\n\n"
            f"{expired_text}"
            f"<b>🎫 Daily Tokens:</b> <code>{tokens_left} / {daily_limit}</code>\n"
            f"<b>📦 File Size Limit:</b> <code>2 GB</code>\n"
            f"<b>📊 Total Lifetime Saves:</b> <code>{total_saves}</code>\n\n"
            "<i>Upgrade to Premium for unlimited access! 🚀</i>"
        )

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 View Premium Plans", callback_data="premium_plans_btn")],
        [InlineKeyboardButton("📞 Contact Admin", url="https://t.me/SmartBoy_ApnaMS")]
    ])

    await message.reply_text(
        plan_text,
        reply_markup=buttons,
        parse_mode=enums.ParseMode.HTML
    )

# /premium - Premium Plans Information
@Client.on_message(filters.command("premium") & filters.private)
async def premium_info(client: Client, message: Message):
    await show_premium_plans(message)

# ======================================================
# PREMIUM PLANS VIEW (Reusable)
# ======================================================

async def show_premium_plans(message_or_query):
    text = (
        "<b>💎Premium Plans</b>\n\n"
        "<blockquote>\n"
        "<b>Why Go Premium?</b>\n"
        "• ♾️ <b>Unlimited</b> Daily Saves\n"
        "• 📂 <b>4GB+</b> File Support\n"
        "• ⚡ <b>Zero</b> Processing Delay\n"
        "• 🖼 <b>Custom</b> Thumbnails & Captions\n"
        "• 👑 <b>Premium</b> Badge\n"
        "</blockquote>\n\n"
        "<b>💲 Pricing:</b>\n"
        "• <b>1 Month:</b> ₹50 / $1\n"
        "• <b>Lifetime:</b> ₹200 / $4\n\n"
        "<i>Tap the button below to buy instantly.</i>"
    )

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Buy Premium Now", url="https://t.me/SmartBoy_ApnaMS")],
        [InlineKeyboardButton("⬅️ Back to My Plan", callback_data="myplan_back_btn")]
    ])

    if isinstance(message_or_query, Message):
        await message_or_query.reply_text(
            text,
            reply_markup=buttons,
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )
    else:
        await message_or_query.edit_message_text(
            text,
            reply_markup=buttons,
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )

# ======================================================
# ADMIN COMMANDS - Secure & Detailed
# ======================================================

@Client.on_message(filters.command("add_premium") & filters.user(OWNER_ID) & filters.private)
async def add_premium_admin(client: Client, message: Message):
    if len(message.command) < 3:
        return await message.reply_text(
            "<b>⚠️ Admin Usage:</b>\n"
            "<code>/add_premium &lt;user_id&gt; &lt;days&gt;</code>\n\n"
            "<i>Use 0 for permanent premium.</i>",
            parse_mode=enums.ParseMode.HTML
        )

    try:
        user_id = int(message.command[1])
        days = int(message.command[2])

        if days == 0:
            expiry_date = None
            duration_text = "Permanent"
        else:
            expiry_date = (date.today() + timedelta(days=days)).isoformat()
            duration_text = f"{days} days (until {_fmt_ist(_to_ist(expiry_date))})"

        # Update DB
        await db.add_premium(user_id, expiry_date)

        await message.reply_text(
            f"<b>✅ Premium Added Successfully</b>\n\n"
            f"<b>User ID:</b> <code>{user_id}</code>\n"
            f"<b>Duration:</b> {duration_text}",
            parse_mode=enums.ParseMode.HTML
        )

    except ValueError:
        await message.reply_text("❌ <b>Error:</b> User ID and Days must be numbers.", parse_mode=enums.ParseMode.HTML)
    except Exception as e:
        await message.reply_text(f"❌ <b>Error:</b> {e}", parse_mode=enums.ParseMode.HTML)

@Client.on_message(filters.command("remove_premium") & filters.user(OWNER_ID) & filters.private)
async def remove_premium_admin(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(
            "<b>⚠️ Usage:</b> <code>/remove_premium &lt;user_id&gt;</code>",
            parse_mode=enums.ParseMode.HTML
        )
    try:
        user_id = int(message.command[1])
        await db.remove_premium(user_id)
        await message.reply_text(f"✅ Premium removed from <code>{user_id}</code>.")
    except Exception as e:
        await message.reply_text(f"Error: {e}")

# ======================================================
# OWNER COMMANDS - Grant/Revoke Temporary Auth Access
# ======================================================

@Client.on_message(filters.command("addauth") & filters.user(OWNER_ID) & filters.private)
async def add_auth_cmd(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(
            "<b>⚠️ Owner Usage:</b>\n"
            "<code>/addauth &lt;user_id&gt; [days]</code>\n\n"
            "<i>Days defaults to 7 if not given. Grants the user unlimited "
            "access (no daily limit, no size limit) until it expires.</i>",
            parse_mode=enums.ParseMode.HTML
        )

    try:
        user_id = int(message.command[1])
        days = int(message.command[2]) if len(message.command) > 2 else 7

        if not await db.is_user_exist(user_id):
            await db.add_user(user_id, str(user_id))

        expiry_dt = datetime.now() + timedelta(days=days)
        await db.add_auth(user_id, expiry_dt)

        await message.reply_text(
            f"<b>✅ Auth Access Granted</b>\n\n"
            f"<b>User ID:</b> <code>{user_id}</code>\n"
            f"<b>Duration:</b> {days} day(s)\n"
            f"<b>Expires:</b> <code>{_fmt_ist(_to_ist(expiry_dt))}</code>",
            parse_mode=enums.ParseMode.HTML
        )
    except ValueError:
        await message.reply_text("❌ <b>Error:</b> User ID and days must be numbers.", parse_mode=enums.ParseMode.HTML)
    except Exception as e:
        await message.reply_text(f"❌ <b>Error:</b> {e}", parse_mode=enums.ParseMode.HTML)

@Client.on_message(filters.command("rmauth") & filters.user(OWNER_ID) & filters.private)
async def remove_auth_cmd(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(
            "<b>⚠️ Usage:</b> <code>/rmauth &lt;user_id&gt;</code>",
            parse_mode=enums.ParseMode.HTML
        )
    try:
        user_id = int(message.command[1])
        await db.remove_auth(user_id)
        await message.reply_text(
            f"<b>✅ Auth Access Removed</b>\n\n<b>User ID:</b> <code>{user_id}</code>",
            parse_mode=enums.ParseMode.HTML
        )
    except ValueError:
        await message.reply_text("❌ <b>Error:</b> User ID must be a number.", parse_mode=enums.ParseMode.HTML)
    except Exception as e:
        await message.reply_text(f"❌ <b>Error:</b> {e}", parse_mode=enums.ParseMode.HTML)

# ======================================================
# CALLBACK QUERIES
# ======================================================

@Client.on_callback_query(filters.regex("^premium_plans_btn$"))
async def premium_plans_callback(client: Client, callback_query: CallbackQuery):
    await show_premium_plans(callback_query)

@Client.on_callback_query(filters.regex("^myplan_back_btn$"))
async def myplan_back_callback(client: Client, callback_query: CallbackQuery):
    # Pass the message object to reuse logic
    await my_plan(client, callback_query.message, callback_query.from_user)
