# ─────────────────────────────────────────────────────────────────────────
# Force Subscribe
#  - Every channel in FORCE_SUB_CHANNELS (config.py) must be joined to use the bot
#  - The check runs before ANY private message / button press of a user
#  - Joined users are SAVED in MongoDB (collection: fs_members)
#  - When a saved user leaves a channel, the bot DMs them immediately:
#      1) instantly, through Telegram "chat_member" updates
#      2) as a backup, through a periodic membership sweep (FORCE_SUB_SWEEP_SECONDS)
#  - Personal single-use invite links are created per user
# ─────────────────────────────────────────────────────────────────────────
import asyncio
import html
import re
import time
from datetime import datetime, timedelta

from pyrogram import Client, filters, enums
from pyrogram.errors import (
    UserNotParticipant,
    PeerIdInvalid,
    ChannelInvalid,
    ChannelPrivate,
)
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ChatMemberUpdated,
    Message,
    CallbackQuery,
)

import config
from config import OWNER_ID
from database.db import db
from logger import LOGGER

logger = LOGGER(__name__)

FORCE_SUB_ENABLED = bool(getattr(config, "FORCE_SUB_ENABLED", True))
EXEMPT_OWNER = bool(getattr(config, "FORCE_SUB_EXEMPT_OWNER", True))
SWEEP_SECONDS = int(getattr(config, "FORCE_SUB_SWEEP_SECONDS", 60))

INVITE_TTL_SEC = 24 * 60 * 60   # personal invite link is valid for 24 hours
ALERT_GAP_SEC = 6 * 60 * 60     # same owner alert at most once per 6 hours
LEFT_DM_GAP_SEC = 10 * 60       # never DM the same user+channel twice within 10 minutes
PROMPT_GAP_SEC = 3              # do not spam the prompt if the user sends many messages
PASS_CACHE_SEC = 15             # a user who just passed the check is not re-checked for 15s

_IN_STATUSES = (
    enums.ChatMemberStatus.OWNER,
    enums.ChatMemberStatus.ADMINISTRATOR,
    enums.ChatMemberStatus.MEMBER,
)


# ── Read channels from config (placeholder / invalid chat_id are ignored) ──
def _load_channels():
    channels, skipped = [], []
    for i, c in enumerate(getattr(config, "FORCE_SUB_CHANNELS", None) or []):
        if not isinstance(c, dict):
            continue
        raw = str(c.get("chat_id", "")).strip()
        title = str(c.get("title") or f"Channel {i + 1}").strip()
        if not re.fullmatch(r"-100\d{6,}", raw):
            skipped.append(title)
            continue
        channels.append(
            {"title": title, "link": str(c.get("link") or "").strip(), "chat_id": int(raw)}
        )
    if skipped:
        logger.warning(f"[ForceSub] chat_id not filled, channels ignored: {', '.join(skipped)}")
    return channels


CHANNELS = _load_channels()
BY_ID = {c["chat_id"]: c for c in CHANNELS}


def enabled() -> bool:
    return FORCE_SUB_ENABLED and bool(CHANNELS)


def is_exempt(user_id: int) -> bool:
    return EXEMPT_OWNER and user_id == OWNER_ID


# ── Saved "this user is joined in this channel" records ──
_col = db.db.fs_members
_index_ready = False


async def _ensure_index():
    global _index_ready
    if _index_ready:
        return
    _index_ready = True
    try:
        await _col.create_index([("user_id", 1), ("chat_id", 1)], unique=True)
    except Exception as e:
        logger.warning(f"[ForceSub] index creation skipped: {e}")


async def mark_joined(user_id: int, chat_id: int):
    try:
        await _ensure_index()
        await _col.update_one(
            {"user_id": user_id, "chat_id": chat_id},
            {"$setOnInsert": {"joined_at": datetime.now()}},
            upsert=True,
        )
    except Exception as e:
        if "E11000" not in str(e):
            logger.error(f"[ForceSub] save joined failed: {e}")


async def unmark(user_id: int, chat_id: int):
    try:
        await _col.delete_one({"user_id": user_id, "chat_id": chat_id})
    except Exception as e:
        logger.error(f"[ForceSub] delete record failed: {e}")


# ── helpers ──
_LINK_CACHE = {}    # (chat_id, user_id) -> (url, expires_at)
_ALERTED_AT = {}    # key -> timestamp
_LEFT_DM_AT = {}    # (user_id, chat_id) -> timestamp
_PROMPT_AT = {}     # user_id -> timestamp
_PASSED_AT = {}     # user_id -> timestamp


def _is_in(member) -> bool:
    if member is None:
        return False
    if member.status in _IN_STATUSES:
        return True
    if member.status == enums.ChatMemberStatus.RESTRICTED:
        return bool(getattr(member, "is_member", True))
    return False


async def alert_owner(client: Client, key: str, text: str):
    now = time.time()
    if now - _ALERTED_AT.get(key, 0) < ALERT_GAP_SEC:
        return
    _ALERTED_AT[key] = now
    logger.warning("[ForceSub] " + re.sub(r"<[^>]+>", "", text))
    try:
        await client.send_message(
            OWNER_ID, f"⚠️ <b>Force Subscribe Alert</b>\n\n{text}", parse_mode=enums.ParseMode.HTML
        )
    except Exception:
        pass  # the owner has not started the bot - ignore


async def _get_member(client: Client, chat_id: int, user_id: int):
    try:
        return await client.get_chat_member(chat_id, user_id)
    except (PeerIdInvalid, ChannelInvalid):
        # the bot has not "seen" this channel yet: resolve it once, then retry
        await client.get_chat(chat_id)
        return await client.get_chat_member(chat_id, user_id)


async def get_join_link(client: Client, ch: dict, user_id: int, fresh: bool = False) -> str:
    key = (ch["chat_id"], user_id)
    cached = _LINK_CACHE.get(key)
    if not fresh and cached and cached[1] > time.time() + 60:
        return cached[0]
    try:
        link = await client.create_chat_invite_link(
            ch["chat_id"],
            name=f"u{user_id}"[:32],
            expire_date=datetime.now() + timedelta(seconds=INVITE_TTL_SEC),
            member_limit=1,
        )
        if len(_LINK_CACHE) > 5000:
            now = time.time()
            for k in [k for k, v in _LINK_CACHE.items() if v[1] < now]:
                _LINK_CACHE.pop(k, None)
        _LINK_CACHE[key] = (link.invite_link, time.time() + INVITE_TTL_SEC)
        return link.invite_link
    except Exception as e:
        await alert_owner(
            client,
            f"invite:{ch['chat_id']}",
            f"Could not create an invite link for <b>{html.escape(ch['title'])}</b> "
            f"(<code>{ch['chat_id']}</code>): {html.escape(str(e))}\n"
            "Make the bot an admin there with the \"Invite Users\" permission. "
            "Until then the link from config.py is used.",
        )
        return ch["link"]


async def get_missing(client: Client, user_id: int) -> list:
    """Channels this user has NOT joined (also saves / removes the joined records)."""

    async def check(ch):
        try:
            member = await _get_member(client, ch["chat_id"], user_id)
            return ch, _is_in(member), False
        except UserNotParticipant:
            return ch, False, False
        except Exception as e:
            # Config problem (bot not admin / wrong chat_id): skip that channel instead of
            # locking every user out of the bot.
            await alert_owner(
                client,
                f"check:{ch['chat_id']}",
                f"Could not check membership in <b>{html.escape(ch['title'])}</b> "
                f"(<code>{ch['chat_id']}</code>): {html.escape(str(e))}\n"
                "Make the bot an admin in that channel and verify the chat_id. "
                "This channel is skipped until it is fixed.",
            )
            return ch, True, True

    results = await asyncio.gather(*(check(ch) for ch in CHANNELS))
    missing = []
    for ch, joined, failed in results:
        if failed:
            continue
        if joined:
            _LINK_CACHE.pop((ch["chat_id"], user_id), None)
            await mark_joined(user_id, ch["chat_id"])
        else:
            await unmark(user_id, ch["chat_id"])
            missing.append(ch)
    if not missing:
        _PASSED_AT[user_id] = time.time()
    return missing


async def build_prompt(client: Client, user, missing: list):
    name = html.escape(user.first_name or "User")
    text = (
        f"<blockquote><b>HEY {name}</b></blockquote>\n\n"
        "<b>JOIN OUR CHANNELS FIRST ‼️ THEN USE THE BOT</b>\n\n"
        "<i>Join all the channels below, then press 🔄 TRY AGAIN.</i>"
    )
    links = await asyncio.gather(*(get_join_link(client, ch, user.id) for ch in missing))
    buttons = [
        InlineKeyboardButton(f"⭐ {ch['title']}", url=url)
        for ch, url in zip(missing, links)
        if url
    ]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton("🔄 TRY AGAIN", callback_data="fs_retry")])
    return text, InlineKeyboardMarkup(rows)


async def _send_prompt(client: Client, user, chat_id: int, missing: list):
    now = time.time()
    if now - _PROMPT_AT.get(user.id, 0) < PROMPT_GAP_SEC:
        return
    _PROMPT_AT[user.id] = now
    text, markup = await build_prompt(client, user, missing)
    await client.send_message(
        chat_id,
        text,
        reply_markup=markup,
        parse_mode=enums.ParseMode.HTML,
        disable_web_page_preview=True,
    )


# ── GATE: runs before every other handler (group=-2) ──
@Client.on_message(filters.private & filters.incoming, group=-2)
async def fs_gate_message(client: Client, message: Message):
    user = message.from_user
    if not user or not enabled() or is_exempt(user.id):
        return
    if time.time() - _PASSED_AT.get(user.id, 0) < PASS_CACHE_SEC:
        return
    try:
        missing = await get_missing(client, user.id)
        if not missing:
            return
        await _send_prompt(client, user, message.chat.id, missing)
    except Exception as e:
        logger.error(f"[ForceSub] gate error: {e}")
        return  # on an unexpected error never take the whole bot down
    message.stop_propagation()


@Client.on_callback_query(~filters.regex(r"^fs_retry$"), group=-2)
async def fs_gate_callback(client: Client, callback_query: CallbackQuery):
    user = callback_query.from_user
    if not user or not enabled() or is_exempt(user.id):
        return
    if time.time() - _PASSED_AT.get(user.id, 0) < PASS_CACHE_SEC:
        return
    try:
        missing = await get_missing(client, user.id)
        if not missing:
            return
        await callback_query.answer("❗ Join all the required channels first.", show_alert=True)
        await _send_prompt(client, user, user.id, missing)
    except Exception as e:
        logger.error(f"[ForceSub] callback gate error: {e}")
        return
    callback_query.stop_propagation()


# ── TRY AGAIN button ──
@Client.on_callback_query(filters.regex(r"^fs_retry$"), group=-2)
async def fs_retry(client: Client, callback_query: CallbackQuery):
    user = callback_query.from_user
    missing = []
    if enabled() and not is_exempt(user.id):
        _PASSED_AT.pop(user.id, None)
        missing = await get_missing(client, user.id)

    if missing:
        try:
            await callback_query.answer(
                "❗ Join all the channels first, then press TRY AGAIN.", show_alert=True
            )
            text, markup = await build_prompt(client, user, missing)
            await callback_query.message.edit_text(
                text,
                reply_markup=markup,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True,
            )
        except Exception:
            pass  # e.g. MESSAGE_NOT_MODIFIED
    else:
        try:
            await callback_query.answer("✅ Thanks for joining!")
        except Exception:
            pass
        try:
            await callback_query.message.delete()
        except Exception:
            pass
        try:
            await client.send_message(
                user.id,
                "✅ <b>Thanks for joining!</b>\n\nYou can use the bot now. "
                "Send /start or paste your link.",
                parse_mode=enums.ParseMode.HTML,
            )
        except Exception:
            pass
    callback_query.stop_propagation()


# ── The user left a force-sub channel: DM them right away ──
async def notify_left(client: Client, ch: dict, user_id: int):
    key = (user_id, ch["chat_id"])
    now = time.time()
    if now - _LEFT_DM_AT.get(key, 0) < LEFT_DM_GAP_SEC:
        return
    _LEFT_DM_AT[key] = now
    _PASSED_AT.pop(user_id, None)
    try:
        _LINK_CACHE.pop((ch["chat_id"], user_id), None)
        link = await get_join_link(client, ch, user_id, fresh=True)
        text = (
            f"😡 <b>Dude, why you left from this {html.escape(ch['title'])}?</b>\n\n"
            "Please join it again, otherwise you can't use me."
        )
        markup = (
            InlineKeyboardMarkup([[InlineKeyboardButton(f"✅ Join Now - {ch['title']}", url=link)]])
            if link
            else None
        )
        await client.send_message(
            user_id,
            text,
            reply_markup=markup,
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True,
        )
        logger.info(f"[ForceSub] left-DM sent: user {user_id} left {ch['title']}")
    except Exception as e:
        # the user never started the bot or has blocked it - the DM cannot be delivered
        logger.info(f"[ForceSub] left-DM skipped: {e}")


# ── Instant detection through Telegram chat member updates ──
@Client.on_chat_member_updated()
async def fs_member_updated(client: Client, update: ChatMemberUpdated):
    try:
        ch = BY_ID.get(update.chat.id) if update.chat else None
        if not ch or not enabled():
            return
        old, new = update.old_chat_member, update.new_chat_member
        member = new or old
        user = getattr(member, "user", None)
        if not user or user.is_bot:
            return
        logger.info(
            f"[ForceSub] chat_member: user {user.id} "
            f"{old.status.name if old else 'NONE'} -> {new.status.name if new else 'NONE'} "
            f"in {ch['title']}"
        )

        # User joined: save it
        if _is_in(new):
            _LINK_CACHE.pop((ch["chat_id"], user.id), None)
            if not is_exempt(user.id):
                await mark_joined(user.id, ch["chat_id"])
            return

        # User is no longer in the channel: remove the saved record
        await unmark(user.id, ch["chat_id"])

        # DM only for a real "left" (not for ban/kick)
        banned = new is not None and new.status == enums.ChatMemberStatus.BANNED
        if banned or not _is_in(old) or is_exempt(user.id):
            return
        await notify_left(client, ch, user.id)
    except Exception as e:
        logger.error(f"[ForceSub] chat_member error: {e}")


# ── Backup detection: re-check every saved joined user periodically ──
_sweeping = False


async def sweep(client: Client):
    global _sweeping
    if _sweeping or not enabled():
        return
    _sweeping = True
    try:
        ids = [c["chat_id"] for c in CHANNELS]
        records = await _col.find({"chat_id": {"$in": ids}}).to_list(length=None)
        n = 0
        for rec in records:
            ch = BY_ID.get(rec.get("chat_id"))
            uid = rec.get("user_id")
            if not ch or uid is None or is_exempt(uid):
                continue
            try:
                member = await _get_member(client, ch["chat_id"], uid)
                joined = _is_in(member)
                banned = member.status == enums.ChatMemberStatus.BANNED
            except UserNotParticipant:
                joined, banned = False, False
            except Exception:
                continue  # temporary API error - try again in the next sweep
            if not joined:
                await unmark(uid, ch["chat_id"])
                if not banned:
                    await notify_left(client, ch, uid)
            n += 1
            if n % 20 == 0:
                await asyncio.sleep(1)  # stay under Telegram rate limits
    except Exception as e:
        logger.error(f"[ForceSub] sweep error: {e}")
    finally:
        _sweeping = False


_sweeper_started = False


async def _sweep_loop(client: Client):
    while True:
        await asyncio.sleep(SWEEP_SECONDS)
        try:
            await sweep(client)
        except Exception as e:
            logger.error(f"[ForceSub] sweep loop error: {e}")


async def _startup_check(client: Client):
    """Is the bot an admin in every force-sub channel?"""
    try:
        me = await client.get_me()
        for ch in CHANNELS:
            try:
                m = await _get_member(client, ch["chat_id"], me.id)
                if m.status not in (enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER):
                    await alert_owner(
                        client,
                        f"admin:{ch['chat_id']}",
                        f"The bot is not an admin in <b>{html.escape(ch['title'])}</b> "
                        f"(<code>{ch['chat_id']}</code>). Make it an admin, otherwise membership "
                        "checks and invite links will not work.",
                    )
                else:
                    logger.info(f"[ForceSub] OK: {ch['title']} ({ch['chat_id']})")
            except Exception as e:
                await alert_owner(
                    client,
                    f"admin:{ch['chat_id']}",
                    f"Cannot access <b>{html.escape(ch['title'])}</b> (<code>{ch['chat_id']}</code>): "
                    f"{html.escape(str(e))}\nIs the chat_id correct? Is the bot an admin of the channel?",
                )
    except Exception as e:
        logger.error(f"[ForceSub] startup check failed: {e}")


def start_background(client: Client):
    """Called once from bot.py after the bot has logged in."""
    global _sweeper_started
    if _sweeper_started:
        return
    _sweeper_started = True
    if not FORCE_SUB_ENABLED:
        logger.info("[ForceSub] disabled (FORCE_SUB_ENABLED=False)")
        return
    if not CHANNELS:
        logger.info("[ForceSub] no valid channel configured - force subscribe is off")
        return
    asyncio.create_task(_startup_check(client))
    if SWEEP_SECONDS > 0:
        asyncio.create_task(_sweep_loop(client))
        logger.info(f"[ForceSub] leave-sweep every {SWEEP_SECONDS}s")
    logger.info(f"[ForceSub] enabled with {len(CHANNELS)} channel(s)")
