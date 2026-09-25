import motor.motor_asyncio
import datetime
from config import DB_NAME, DB_URI, OWNER_ID
from logger import LOGGER
logger = LOGGER(__name__)
class Database:
   
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db.users
    def new_user(self, id, name):
        return dict(
            id = id,
            name = name,
            session = None,
            daily_usage = 0, # Added: Track saves
            limit_reset_time = None # Added: Track 24h reset time
        )
   
    async def add_user(self, id, name):
        user = self.new_user(id, name)
        await self.col.insert_one(user)
        logger.info(f"New user added to DB: {id} - {name}")
   
    async def is_user_exist(self, id):
        user = await self.col.find_one({'id':int(id)})
        return bool(user)
   
    async def total_users_count(self):
        count = await self.col.count_documents({})
        return count
    async def get_all_users(self):
        return self.col.find({})
    async def delete_user(self, user_id):
        await self.col.delete_many({'id': int(user_id)})
        logger.info(f"User deleted from DB: {user_id}")
    async def set_session(self, id, session):
        await self.col.update_one({'id': int(id)}, {'$set': {'session': session}})
    async def get_session(self, id):
        user = await self.col.find_one({'id': int(id)})
        return user.get('session')
    # Caption Support
    async def set_caption(self, id, caption):
        await self.col.update_one({'id': int(id)}, {'$set': {'caption': caption}})
    async def get_caption(self, id):
        user = await self.col.find_one({'id': int(id)})
        return user.get('caption', None)
    async def del_caption(self, id):
        await self.col.update_one({'id': int(id)}, {'$unset': {'caption': ""}})
    # Thumbnail Support
    async def set_thumbnail(self, id, thumbnail):
        await self.col.update_one({'id': int(id)}, {'$set': {'thumbnail': thumbnail}})
    async def get_thumbnail(self, id):
        user = await self.col.find_one({'id': int(id)})
        return user.get('thumbnail', None)
    async def del_thumbnail(self, id):
        await self.col.update_one({'id': int(id)}, {'$unset': {'thumbnail': ""}})
    # cantarella / Modified by You
    # Don't Remove Credit
    # Telegram Channel @cantarellabots
    # Premium Support
    async def add_premium(self, id, expiry_date):
        # When user buys premium, we also reset their limits just in case
        await self.col.update_one({'id': int(id)}, {
            '$set': {
                'is_premium': True,
                'premium_expiry': expiry_date,
                'daily_usage': 0,
                'limit_reset_time': None
            }
        })
        logger.info(f"User {id} granted premium until {expiry_date}")
    async def remove_premium(self, id):
        await self.col.update_one({'id': int(id)}, {'$set': {'is_premium': False, 'premium_expiry': None}})
        logger.info(f"User {id} removed from premium")
    async def check_premium(self, id):
        user = await self.col.find_one({'id': int(id)})
        if user and user.get('is_premium'):
            return user.get('premium_expiry')
        return None
    async def get_premium_users(self):
        return self.col.find({'is_premium': True})
    # Auth Support (owner-granted temporary unlimited access)
    async def add_auth(self, id, expiry_datetime):
        # Owner-granted auth: also reset limits so it kicks in immediately
        await self.col.update_one(
            {'id': int(id)},
            {'$set': {
                'is_auth': True,
                'auth_expiry': expiry_datetime,
                'daily_usage': 0,
                'limit_reset_time': None
            }},
            upsert=True
        )
        logger.info(f"User {id} granted auth until {expiry_datetime}")
    async def remove_auth(self, id):
        await self.col.update_one({'id': int(id)}, {'$set': {'is_auth': False, 'auth_expiry': None}})
        logger.info(f"User {id} auth access removed")
    async def check_auth(self, id):
        """
        Returns True if the user has active (non-expired) owner-granted auth.
        Auto-clears auth if the expiry time has passed.
        """
        user = await self.col.find_one({'id': int(id)})
        if not user or not user.get('is_auth'):
            return False
        expiry = user.get('auth_expiry')
        if expiry is None:
            return True  # Permanent auth
        if datetime.datetime.now() >= expiry:
            await self.col.update_one({'id': int(id)}, {'$set': {'is_auth': False, 'auth_expiry': None}})
            return False
        return True
    async def has_unlimited_access(self, id):
        """
        Single source of truth for 'no restrictions' access.
        True for: the bot OWNER, active paid premium,
        or active owner-granted auth.
        """
        if int(id) == OWNER_ID:
            return True
        if await self.check_premium(id):
            return True
        if await self.check_auth(id):
            return True
        return False
    # Ban Support
    async def ban_user(self, id):
        await self.col.update_one({'id': int(id)}, {'$set': {'is_banned': True}})
        logger.warning(f"User banned: {id}")
    async def unban_user(self, id):
        await self.col.update_one({'id': int(id)}, {'$set': {'is_banned': False}})
        logger.info(f"User unbanned: {id}")
    async def is_banned(self, id):
        user = await self.col.find_one({'id': int(id)})
        return user.get('is_banned', False)
    # Dump Chat Support
    async def set_dump_chat(self, id, chat_id):
        await self.col.update_one({'id': int(id)}, {'$set': {'dump_chat': int(chat_id)}})
    async def get_dump_chat(self, id):
        user = await self.col.find_one({'id': int(id)})
        return user.get('dump_chat', None)
    # Delete/Replace Words Support
    async def set_delete_words(self, id, words):
        await self.col.update_one({'id': int(id)}, {'$addToSet': {'delete_words': {'$each': words}}})
    async def get_delete_words(self, id):
        user = await self.col.find_one({'id': int(id)})
        return user.get('delete_words', [])
    async def remove_delete_words(self, id, words):
        await self.col.update_one({'id': int(id)}, {'$pull': {'delete_words': {'$in': words}}})
    async def set_replace_words(self, id, repl_dict):
        user = await self.col.find_one({'id': int(id)})
        current_repl = user.get('replace_words', {})
        current_repl.update(repl_dict)
        await self.col.update_one({'id': int(id)}, {'$set': {'replace_words': current_repl}})
    async def get_replace_words(self, id):
        user = await self.col.find_one({'id': int(id)})
        return user.get('replace_words', {})
    async def remove_replace_words(self, id, words):
        user = await self.col.find_one({'id': int(id)})
        current_repl = user.get('replace_words', {})
        for w in words:
            current_repl.pop(w, None)
        await self.col.update_one({'id': int(id)}, {'$set': {'replace_words': current_repl}})
    # --------------------------------------------------------
    # NEW FEATURES: Daily Limits (Free User Restriction)
    # --------------------------------------------------------
    async def check_limit(self, id):
        """
        Checks if a user has hit their daily limit.
        Returns: True if BLOCKED (limit reached), False if ALLOWED.
        """
        # 0. Unlimited access check: config admins/owner, premium, or owner-granted auth
        if await self.has_unlimited_access(id):
            return False
        user = await self.col.find_one({'id': int(id)})
        if not user:
            return False # Should be added via add_user, but safe fallback
       
        # 1. Premium Check: Always allowed
        if user.get('is_premium'):
            return False
        # 2. Check Time Reset
        now = datetime.datetime.now()
        reset_time = user.get('limit_reset_time')
       
        # If reset time has passed or was never set, reset count to 0
        if reset_time is None or now >= reset_time:
            await self.col.update_one(
                {'id': int(id)},
                {'$set': {'daily_usage': 0, 'limit_reset_time': None}}
            )
            return False # Allowed (count is 0)
        # 3. Check Count
        usage = user.get('daily_usage', 0)
        if usage >= 5:
            return True # Blocked
       
        return False # Allowed
    async def add_traffic(self, id):
        """
        Increments usage count.
        If it's the first save of the cycle, sets the 24h timer.
        """
        # If unlimited (config admin/owner, premium, or active auth), skip usage tracking
        if await self.has_unlimited_access(id):
            return
        user = await self.col.find_one({'id': int(id)})
        if not user:
            return
        now = datetime.datetime.now()
        reset_time = user.get('limit_reset_time')
        # Logic: If timer is not running (None), start it for 24 hours from NOW.
        if reset_time is None:
            new_reset_time = now + datetime.timedelta(hours=24)
            await self.col.update_one(
                {'id': int(id)},
                {'$set': {'daily_usage': 1, 'limit_reset_time': new_reset_time}}
            )
        else:
            # Just increment
            await self.col.update_one(
                {'id': int(id)},
                {'$inc': {'daily_usage': 1}}
            )
db = Database(DB_URI, DB_NAME)
