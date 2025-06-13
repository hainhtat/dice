import logging
import asyncio # For async.sleep
from datetime import datetime
import random # For random.randint fallback in dice roll
import re # Import the 're' module for regex operations

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes # Only ContextTypes is needed here from telegram.ext

# Import necessary components, re-add get_chat_data_for_id
from game_logic import DiceGame, WAITING_FOR_BETS, GAME_CLOSED, GAME_OVER, get_chat_data_for_id # Re-add get_chat_data_for_id
from constants import global_data, HARDCODED_ADMINS, RESULT_EMOJIS, INITIAL_PLAYER_SCORE, ALLOWED_GROUP_IDS

# Configure logging for this module (this will be overridden by main.py's config)
logger = logging.getLogger(__name__)


def is_admin(chat_id, user_id):
    """
    Checks if a user is an administrator in a specific chat
    or if they are one of the hardcoded global administrators.
    """
    # We still need get_chat_data_for_id for the in-memory group_admins
    chat_specific_data = get_chat_data_for_id(chat_id)
    is_chat_admin = user_id in chat_specific_data["group_admins"]
    is_hardcoded_admin = user_id in HARDCODED_ADMINS
    logger.debug(f"is_admin: Checking admin status for user {user_id} in chat {chat_id}: is_chat_admin={is_chat_admin}, is_hardcoded_admin={is_hardcoded_admin}")
    return is_chat_admin or is_hardcoded_admin

async def update_group_admins(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Fetches the current list of administrators for a given chat
    and updates the global_data storage.
    Returns True on success, False on failure.
    """
    try:
        admins = await context.bot.get_chat_administrators(chat_id)
        admin_ids = [admin.user.id for admin in admins]
        
        # We still store group admins in memory for quick access.
        chat_specific_data = get_chat_data_for_id(chat_id)
        chat_specific_data["group_admins"] = admin_ids # Update chat-specific admin list
        
        logger.info(f"update_group_admins: Updated admin list for chat {chat_id}: {admin_ids}")
        return True
    except Exception as e:
        logger.error(f"update_group_admins: Failed to get chat administrators for chat {chat_id}: {e}")
        return False

async def on_chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles updates related to chat members, specifically when the bot
    is added to or removed from a group, or its status changes.
    """
    chat_member_update = update.chat_member
    if not chat_member_update:
        return

    # --- Group ID check for chat member updates ---
    if update.effective_chat.id not in ALLOWED_GROUP_IDS:
        logger.info(f"on_chat_member_update: Ignoring update from disallowed chat ID: {update.effective_chat.id}")
        # Optionally, send a message to the user/group that the bot is not authorized here.
        # await context.bot.send_message(update.effective_chat.id, "This bot is not authorized to run in this group.")
        return
    # --- END Group ID check ---

    if chat_member_update.new_chat_member.user.id == context.bot.id:
        chat_id = chat_member_update.chat.id
        new_status = chat_member_update.new_chat_member.status

        if new_status in ("member", "administrator"):
            logger.info(f"on_chat_member_update: Bot was added to chat {chat_id} or its status changed. New status: {new_status}.")
            if await update_group_admins(chat_id, context):
                await context.bot.send_message(
                    chat_id,
                    "🎉 *အန်စာတုံးဂိမ်းမှ ကြိုဆိုပါတယ်။* 🎉\n"
                    "ကဲ... ကံစမ်းဖို့ အန်စာတုံး လှိမ့်ကြရအောင်။ ဘော့တ်ရဲ့ အုပ်ချုပ်သူတွေက /startdice နဲ့ ဂိမ်းစနိုင်ပါတယ်။ ကျန်ကစားသမားများကတော့ /score နဲ့ ကိုယ့်ရမှတ်တွေ စစ်ပြီး လောင်းကြေးထပ်နိုင်ပါပြီ။ အားလုံးပဲ ကံကောင်းကြပါစေ!\n",
                    parse_mode="Markdown"
                )
            else:
                await context.bot.send_message(
                    chat_id,
                    "👋 ဟိုင်း! ကျွန်တော်က အန်စာတုံးဂိမ်းဘော့တ်ပါ။ 😔 အုပ်ချုပ်သူစာရင်းကို ရှာမတွေ့လို့ စိတ်မကောင်းပါ။ 'ချတ်အုပ်ချုပ်သူများကို ရယူရန်' ခွင့်ပြုချက် ပေးထားလား သေချာစစ်ပေးပါဦး။",
                    parse_mode="Markdown"
                )
        elif new_status == "left":
            logger.info(f"on_chat_member_update: Bot was removed from chat {chat_id}.")
            # Clean all chat-specific data in global_data
            if chat_id in global_data["all_chat_data"]:
                del global_data["all_chat_data"][chat_id]
                logger.info(f"on_chat_member_update: Cleaned all_chat_data for chat {chat_id}.")
            if chat_id in context.chat_data:
                del context.chat_data[chat_id]
                logger.info(f"on_chat_member_update: Cleaned context.chat_data for chat {chat_id}.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles the /start command, sending a welcoming, more descriptive message
    and instructions to the user.
    """
    chat_id = update.effective_chat.id
    # --- Group ID check ---
    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"start: Ignoring command from disallowed chat ID: {chat_id}")
        await update.message.reply_text(f"ဆောရီးနော်၊ ကျွန်တော်က ဒီ group ({chat_id}) မှာ ကစားဖို့ ခွင့်ပြုချက်မရှိပါဘူး။ ခွင့်ပြုထားတဲ့ group ထဲ ထည့်ပေးပါဦးနော်။", parse_mode="Markdown")
        return
    # --- END Group ID check ---

    user_id = update.effective_user.id
    logger.info(f"start: Received /start command from user {user_id} in chat {chat_id}")

    await update.message.reply_text(
        "🌟🎲 *Rangoon Dice Showdown မှ ကြိုဆိုပါတယ်ဗျို့!* �🌟\n\n"
        "ကဲ... ဘယ်သူ့ကံက အသားဆုံးလဲ စိန်ခေါ်လိုက်ရအောင်! ကစားနည်းလေးကတော့:\n\n"
        "✨ *ဂိမ်းစည်းမျဉ်းတွေ* က ရိုးရှင်းပါတယ်။ အန်စာတုံး ၂ လုံးလှိမ့်ပြီး ပေါင်းလဒ်ကို ခန့်မှန်းရုံပဲ!\n"
        "  - *BIG* 🔼: ၇ ထက်ကြီးရင် (၂ ဆ ပြန်ရမယ်နော်!)\n"
        "  - *SMALL* 🔽: ၇ ထက်ငယ်ရင် (ဒါလည်း ၂ ဆ ပြန်ရမယ်!)\n"
        "  - *LUCKY* 🍀: အတိအကျ ၇ ထွက်ရင် (ဒါဆို ၅ ဆတောင် ပြန်ရမှာ!)\n\n"
        "💰 *ဘယ်လိုလောင်းမလဲ:*\n"
        "  - လောင်းကြေးထပ်ချိန် (အမှတ် ၁၀၀ က စပြီး) အတွင်း ခလုတ်လေးတွေနှိပ်ပြီး လောင်းလို့ရတယ်။\n"
        "  - ဒါမှမဟုတ် စာနဲ့ရိုက်ပြီး လောင်းချင်ရင်: `/b <ပမာဏ>`, `/s <ပမာဏ>`, `/l <ပမာဏ>` လို့ ရိုက်ရမယ်နု့်!\n"
        "    (ဥပမာ: `big 500` (သို့) `small100` (သို့) `lucky 250`)\n"
        "  _မှတ်ထားနော်! တစ်ပွဲတည်းမှာ မတူညီတဲ့ ရလဒ်တွေပေါ် အကြိမ်ကြိမ် လောင်းကြေးထပ်လို့ရတယ်နော်။_ \n\n"
        "📊 * command လေးတွေက:*\n"
        "  - /score: ကိုယ့်ရမှတ် ဘယ်လောက်ရှိပြီလဲ ကြည့်ချင်ရင်။\n"
        "  - /stats: ကိုယ်ဘယ်နှစ်ပွဲနိုင်၊ ဘယ်နှစ်ပွဲရှုံးလဲ အသေးစိတ်ကြည့်မယ်ဆိုရင်။\n"
        "  - /leaderboard: ဒီ group ရဲ့ အချမ်းသာဆုံး ကစားသမားတွေကို ကြည့်မယ်ဆိုရင်။\n"
        "  - /history: မကြာသေးခင်က ဘယ်ပွဲတွေမှာ ဘာရလဒ်တွေ ထွက်ခဲ့လဲ ကြည့်မယ်ဆိုရင်။\n\n"
        "👑 *Admin များအတွက် command:* (Admin တွေပဲ သုံးလို့ရမယ်နော်!)\n"
        "  - /startdice: အန်စာတုံးပွဲအသစ် စတင်မယ်ဆိုရင်။\n"
        "  - /adjustscore <user\\_id> <amount>: ကစားသမားတစ်ယောက်ရဲ့ ရမှတ်ကို ထပ်ပေးတာ/နုတ်တာ လုပ်ချင်ရင်။\n"
        "  - /checkscore <user\\_id or @username>: ကစားသမားတစ်ယောက်ရဲ့ ရမှတ်နဲ့ အသေးစိတ်အချက်အလက်တွေ စစ်ချင်ရင်။\n"
        "  - /stop: လက်ရှိဂိမ်းကို ရပ်ပြီး လောင်းထားတဲ့အမှတ်တွေကို ပြန်အမ်းချင်ရင်။\n\n"
        "ကံတရားက သင့်ဘက်မှာ အမြဲရှိနေပါစေ! 😉",
        parse_mode="Markdown"
    )

async def _start_interactive_game_round(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """
    Helper function to initiate a single interactive game round.
    This logic is extracted to be reusable for both single /startdice and sequential games.
    """
    # --- Group ID check ---
    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"_start_interactive_game_round: Ignoring action from disallowed chat ID: {chat_id}")
        return
    # --- END Group ID check ---

    # Match counter from in-memory global_data
    chat_specific_data = get_chat_data_for_id(chat_id)
    match_id = chat_specific_data["match_counter"] # Get chat-specific match counter
    chat_specific_data["match_counter"] += 1 # Increment chat-specific match counter
    
    game = DiceGame(match_id, chat_id)
    context.chat_data[chat_id] = {"game": game} # Store the game instance in chat-specific data

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("BIG 🔼 (Total > 7)", callback_data="bet_big"),
            InlineKeyboardButton("SMALL 🔽 (Total < 7)", callback_data="bet_small"),
            InlineKeyboardButton("LUCKY 🍀 (Total = 7)", callback_data="bet_lucky")
        ]
    ])

    await context.bot.send_message(
        chat_id,
        f"🔥 *ပွဲစဉ် #{match_id}: လောင်းကြေးဖွင့်ပါပြီ!* 🔥\n\n"
        "💰 BIG (>7), SMALL (<7), ဒါမှမဟုတ် LUCKY (အတိအကျ 7) တို့ပေါ် လောင်းကြေးထပ်လိုက်တော့!\n"
        "ခလုတ်လေးတွေနှိပ်ပြီး (အမှတ် ၁၀၀) လောင်းလို့ရသလို၊ `big 250`, `s 50`, `lucky100` လိုမျိုးလည်း ရိုက်ပြီး လောင်းနိုင်တယ်။\n"
        "_တစ်ပွဲတည်းမှာ မတူညီတဲ့ ရလဒ်တွေပေါ် အကြိမ်ကြိမ် လောင်းကြေးထပ်လို့ရတယ်နော်။_ \n\n"
        "⏳ လောင်းကြေးပိတ်ဖို့ *စက္ကန့် ၆၀* ပဲကျန်တော့မယ်! ကံတရားက ဘယ်သူ့ဘက်မှာလဲ ကြည့်ရအောင်!",
        parse_mode="Markdown", reply_markup=keyboard
    )
    logger.info(f"_start_interactive_game_round: Match {match_id} started successfully in chat {chat_id}. Betting open for 60 seconds.")

    # Store the job for potential cancellation
    close_bets_job = context.job_queue.run_once(
        close_bets_scheduled,
        60, # seconds from now
        chat_id=chat_id,
        data=game,
        name=f"close_bets_{chat_id}_{match_id}" # Give job a unique name for cancellation
    )
    context.chat_data[chat_id]["close_bets_job"] = close_bets_job # Store job for cancellation
    logger.info(f"_start_interactive_game_round: Job for close_bets_scheduled scheduled for match {match_id} in chat {chat_id}.")


async def _manage_game_sequence(context: ContextTypes.DEFAULT_TYPE):
    """
    This function is called by the job queue to start the next interactive game in a sequence.
    """
    chat_id = context.job.chat_id
    # --- Group ID check ---
    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"_manage_game_sequence: Ignoring action from disallowed chat ID: {chat_id}")
        return
    # --- END Group ID check ---
    
    # Access sequence state via context.chat_data[chat_id]
    chat_specific_context = context.chat_data.setdefault(chat_id, {})
    num_matches_total = chat_specific_context.get("num_matches_total")
    current_match_index = chat_specific_context.get("current_match_index")

    if num_matches_total is None or current_match_index is None:
        logger.error(f"_manage_game_sequence: Missing sequence state in chat {chat_id}. Aborting sequence.")
        # Clean up existing sequence state if incomplete
        if "num_matches_total" in chat_specific_context: del chat_specific_context["num_matches_total"]
        if "current_match_index" in chat_specific_context: del chat_specific_context["current_match_index"]
        if "game" in chat_specific_context: del chat_specific_context["game"]
        return

    if current_match_index < num_matches_total:
        logger.info(f"_manage_game_sequence: Starting next game in sequence. Match {current_match_index + 1} of {num_matches_total} for chat {chat_id}.")
        chat_specific_context["current_match_index"] += 1
        # Store job for potential cancellation
        next_game_job = context.job_queue.run_once(
            _start_interactive_game_round, # Now this function initiates the round
            2, # Small delay before first game starts
            chat_id=chat_id,
            name=f"start_next_game_{chat_id}_{chat_specific_context['current_match_index']}"
        )
        chat_specific_context["next_game_job"] = next_game_job
        
    else:
        logger.info(f"_manage_game_sequence: All {num_matches_total} matches in sequence completed for chat {chat_id}. Cleaning up.")
        # Clean up context.chat_data[chat_id]
        if "num_matches_total" in chat_specific_context:
            del chat_specific_context["num_matches_total"]
        if "current_match_index" in chat_specific_context:
            del chat_specific_context["current_match_index"]
        if "game" in chat_specific_context:
            del chat_specific_context["game"]
        await context.bot.send_message(
            chat_id,
            "🎉 *စီစဉ်ထားတဲ့ပွဲစဉ်တွေ အားလုံး ပြီးဆုံးသွားပြီဗျို့!* 🎉\n"
            "ဘယ်သူတွေ ချမ်းသာသွားလဲဆိုတာ /leaderboard နဲ့ ကြည့်လိုက်တော့နော်။",
            parse_mode="Markdown"
        )


async def start_dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Starts a new dice game round or multiple automatic rounds.
    Only accessible by administrators.
    Usage: /startdice [number_of_matches]
    - If number_of_matches is provided, plays that many automatic matches.
    - If no number is provided, starts a single interactive betting round.
    """
    chat_id = update.effective_chat.id
    # --- Group ID check ---
    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"start_dice: Ignoring command from disallowed chat ID: {chat_id}")
        await update.message.reply_text(f"ဆောရီးနော်၊ ကျွန်တော်က ဒီ group ({chat_id}) မှာ ကစားဖို့ ခွင့်ပြုချက်မရှိပါဘူး။ ခွင့်ပြုထားတဲ့ group ထဲ ထည့်ပေးပါဦးနော်။", parse_mode="Markdown")
        return
    # --- END Group ID check ---

    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    logger.info(f"start_dice: User {user_id} ({username}) attempting to start a game in chat {chat_id}")

    # Check if admin list for this specific chat is loaded or empty
    # We still need in-memory group_admins for this check.
    if not get_chat_data_for_id(chat_id)["group_admins"]:
        logger.info(f"start_dice: Admin list for chat {chat_id} is empty or not loaded. Attempting to update it now.")
        if not await update_group_admins(chat_id, context):
            await update.message.reply_text(
                "❌ အုပ်စုအုပ်ချုပ်သူစာရင်းကို ရှာမတွေ့လို့ စိတ်မကောင်းပါဘူး။ ကျွန်တော့်ကို 'ချတ်အုပ်ချုပ်သူများကို ရယူရန်' ခွင့်ပြုချက် ပေးထားလား သေချာစစ်ပေးပါဦး။ ပြီးရင် ထပ်ကြိုးစားကြည့်နော်။",
                parse_mode="Markdown"
            )
            return

    if not is_admin(chat_id, user_id):
        logger.warning(f"start_dice: User {user_id} is not an admin and tried to start a game in chat {chat_id}.")
        return await update.message.reply_text("❌ Admin တွေပဲ အန်စာတုံးဂိမ်းအသစ်ကို စတင်လို့ရပါတယ်နော်။", parse_mode="Markdown")

    # Access game state from context.chat_data[chat_id]
    chat_specific_context = context.chat_data.setdefault(chat_id, {})
    current_game = chat_specific_context.get("game")
    if current_game and current_game.state != GAME_OVER:
        logger.warning(f"start_dice: Game already active in chat {chat_id}. State: {current_game.state}")
        return await update.message.reply_text("⚠️ ဟေ့! ဂိမ်းတစ်ခု စနေပြီနော်။ ပြီးအောင်စောင့်ပေးပါဦး ဒါမှမဟုတ် လက်ရှိပွဲပြီးအောင်စောင့်ပေးပါနော်။", parse_mode="Markdown")
    
    if chat_specific_context.get("num_matches_total") is not None:
         return await update.message.reply_text("⚠️ ပွဲစဉ်တွေ ဆက်တိုက်စတင်ထားပြီးသားနော်။ ပြီးဆုံးအောင်စောင့်ပေးပါဦး။", parse_mode="Markdown")


    num_matches_requested = 1

    if context.args:
        try:
            num_matches_requested = int(context.args[0])
            if num_matches_requested <= 0:
                return await update.message.reply_text("❌ ပွဲအရေအတွက်က အပေါင်းကိန်းပြည့် (positive integer) ဖြစ်ရပါမယ်နော်။", parse_mode="Markdown")
            elif num_matches_requested > 20: 
                return await update.message.reply_text("❌ တစ်ကြိမ်တည်းမှာ ဆက်တိုက်အန်စာတုံးပွဲ အပွဲ ၂၀ အထိပဲ စီစဉ်လို့ရပါတယ်။ ဒီထက်ပိုရင် နောက်မှ ဆက်ခေါ်လိုက်နော်။", parse_mode="Markdown")
        except ValueError:
            await update.message.reply_text(
                "ℹ️ `/startdice` အတွက် မှားယွင်းတဲ့ ကိန်းဂဏန်းပါ။ စိတ်မပူပါနဲ့၊ တစ်ပွဲတည်း အန်စာတုံးပွဲ စတင်ပေးပါမယ်နော်။\n"
                "ဘယ်လိုသုံးရမလဲဆိုတော့: `/startdice` က တစ်ပွဲစတင်ဖို့၊ ဒါမှမဟုတ် `/startdice <အရေအတွက်>` ကတော့ ပွဲပေါင်းများစွာ ဆက်တိုက်ကစားဖို့ပါ။",
                parse_mode="Markdown"
            )
            num_matches_requested = 1


    if num_matches_requested > 1:
        # Store sequence state in context.chat_data[chat_id]
        chat_specific_context["num_matches_total"] = num_matches_requested
        chat_specific_context["current_match_index"] = 0

        await update.message.reply_text(
            f"🎮 ကဲ... *{num_matches_requested}* ပွဲ ဆက်တိုက် အန်စာတုံး လောင်းကြေးပွဲတွေ စတင်တော့မယ်! ပထမဆုံးပွဲအတွက် အဆင်သင့်ပြင်ထားလိုက်တော့နော်။",
            parse_mode="Markdown"
        )
        # Store job for potential cancellation
        sequence_job = context.job_queue.run_once(
            _manage_game_sequence,
            2, # Small delay before first game starts
            chat_id=chat_id,
            name=f"manage_sequence_{chat_id}_0"
        )
        chat_specific_context["sequence_job"] = sequence_job # Store the initial job
    else:
        await _start_interactive_game_round(chat_id, context)


async def close_bets_scheduled(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    game = job.data
    chat_id = game.chat_id

    # --- Group ID check ---
    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"close_bets_scheduled: Ignoring action from disallowed chat ID: {chat_id}")
        return
    # --- END Group ID check ---

    logger.info(f"close_bets_scheduled: Job called for match {game.match_id} in chat {chat_id}.")
    
    # Access game instance from context.chat_data[chat_id]
    chat_specific_context = context.chat_data.get(chat_id, {})
    current_game_in_context = chat_specific_context.get("game")
    if current_game_in_context is None or current_game_in_context != game:
        logger.warning(f"close_bets_scheduled: Skipping action for match {game.match_id} in chat {chat_id} as game instance changed or no game. Current game: {current_game_in_context.match_id if current_game_in_context else 'None'}.")
        return

    game.state = GAME_CLOSED
    logger.info(f"close_bets_scheduled: Bets closed for match {game.match_id} in chat {chat_id}. State set to GAME_CLOSED.")
    
    bet_summary_lines = [
        f"⏳ *ပွဲစဉ် #{game.match_id}: လောင်းကြေးတွေ ပိတ်လိုက်ပါပြီနော်!* ⏳\n", 
        "*ဘယ်သူတွေ ဘယ်လောက်လောင်းထားလဲဆိုတော့:*\n"
    ]
    
    has_bets = False
    for bet_type_key, bets_dict in game.bets.items():
        if bets_dict:
            has_bets = True
            bet_summary_lines.append(f"  *{bet_type_key.upper()}* {RESULT_EMOJIS[bet_type_key]}:")
            sorted_bets = sorted(bets_dict.items(), key=lambda item: item[1], reverse=True)
            for uid, amount in sorted_bets:
                # Fetch username from in-memory global_data
                player_info = get_chat_data_for_id(chat_id)["player_stats"].get(uid)
                username_display = player_info['username'].replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`') if player_info else f"User {uid}"
                bet_summary_lines.append(f"    → @{username_display}: *{amount}* မှတ်")
    
    if not has_bets:
        bet_summary_lines.append("  ဒီပွဲမှာ ဘယ်သူမှ မလောင်းထားဘူးဗျို့။ အသည်းအသန်ပဲ!")

    bet_summary_lines.append("\nကဲ... အန်စာတုံးလေးတွေ လှိမ့်လိုက်တော့မယ်! 💥")
    
    try:
        logger.info(f"close_bets_scheduled: Attempting to send 'Bets closed and summary' message for match {game.match_id} to chat {chat_id}.")
        await context.bot.send_message(chat_id, "\n".join(bet_summary_lines), parse_mode="Markdown")
        logger.info(f"close_bets_scheduled: 'Bets closed and summary' message sent successfully for match {game.match_id}.")
    except Exception as e:
        logger.error(f"close_bets_scheduled: Error sending 'Bets closed' message for chat {chat_id}: {e}", exc_info=True)

    # Store the job for potential cancellation
    roll_and_announce_job = context.job_queue.run_once(
        roll_and_announce_scheduled,
        10, # seconds from now
        chat_id=chat_id,
        data=game,
        name=f"roll_and_announce_{chat_id}_{game.match_id}" # Give job a unique name for cancellation
    )
    chat_specific_context["roll_and_announce_job"] = roll_and_announce_job # Store job for cancellation
    logger.info(f"close_bets_scheduled: Job for roll_and_announce_scheduled set for 30 seconds for match {game.match_id} in chat {chat_id}.")
    logger.info(f"close_bets_scheduled: Function finished for match {game.match_id} in chat {chat_id}.")


async def roll_and_announce_scheduled(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    game = job.data
    chat_id = game.chat_id

    # --- Group ID check ---
    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"roll_and_announce_scheduled: Ignoring action from disallowed chat ID: {chat_id}")
        return
    # --- END Group ID check ---

    logger.info(f"roll_and_announce_scheduled: Job called for match {game.match_id} in chat {chat_id}.")
    
    # Access game instance from context.chat_data[chat_id]
    chat_specific_context = context.chat_data.get(chat_id, {})
    current_game_in_context = chat_specific_context.get("game")
    if current_game_in_context is not None and current_game_in_context != game and game.state != GAME_CLOSED:
         logger.warning(f"roll_and_announce_scheduled: Skipping action for match {game.match_id} in chat {chat_id} due to invalid state or game instance change. Current game: {current_game_in_context.match_id if current_game_in_context else 'None'}, Game state: {game.state}.")
         return
    if game.state == GAME_OVER:
        logger.warning(f"roll_and_announce_scheduled: Skipping action for match {game.match_id} as it's already GAME_OVER.")
        return
    
    game.state = GAME_OVER

    d1, d2 = 0, 0

    try:
        logger.info(f"roll_and_announce_scheduled: Sending first animated dice for match {game.match_id}.")
        dice_message_1 = await context.bot.send_dice(chat_id=chat_id)
        d1 = dice_message_1.dice.value
        logger.info(f"roll_and_announce_scheduled: First dice rolled: {d1}.")
        await asyncio.sleep(2)

        logger.info(f"roll_and_announce_scheduled: Sending second animated dice for match {game.match_id}.")
        dice_message_2 = await context.bot.send_dice(chat_id=chat_id)
        d2 = dice_message_2.dice.value
        logger.info(f"roll_and_announce_scheduled: Second dice rolled: {d2}.")
        await asyncio.sleep(1)

    except Exception as e:
        logger.error(f"roll_and_announce_scheduled: Error sending animated dice for chat {chat_id}: {e}", exc_info=True)
        logger.warning("Falling back to random dice values due to Telegram API error.")
        d1, d2 = random.randint(1,6), random.randint(1,6)

    game.result = d1 + d2
    # Call game.payout() (now synchronous)
    winner_type, multiplier, individual_payouts = game.payout(chat_id)

    result_message_text = (
        f"🎉 *ပွဲစဉ် #{game.match_id} ရဲ့ ရလဒ်တွေ ထွက်လာပါပြီဗျို့!* 🎉\n"
        f"🎲 *အန်စာတုံးလှိမ့်လိုက်တော့:* *{d1}* + *{d2}* = *{d1 + d2}* ပဲဗျို့!\n"
        f"🏆 *အနိုင်ရတဲ့ လောင်းကြေး:* *{winner_type.upper()}* {RESULT_EMOJIS[winner_type]} | *{multiplier} ဆ* တောင် ရတာနော်!\n\n"
        "*ဘယ်သူတွေ ဘယ်လောက်ရသွားလဲ ကြည့်ရအောင်:*\n"
    )
    
    # Fetch individual stats from in-memory global_data
    stats = get_chat_data_for_id(chat_id)["player_stats"]
    
    if individual_payouts:
        payout_lines = []
        sorted_payouts = sorted(
            individual_payouts.items(), 
            # Use stats from in-memory global_data for sorting
            key=lambda item: (item[1], stats.get(item[0], {}).get('username', f"User {item[0]}")),
            reverse=True
        )

        for uid, winnings in sorted_payouts:
            # Use stats for player info
            player_info = stats.get(uid)
            if player_info:
                username_display = player_info['username'].replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
                payout_lines.append(f"  ✨ @{username_display}: *+{winnings}* မှတ် (ရမှတ်အသစ်: *{player_info['score']}*)") # Translated points and New score
            else:
                payout_lines.append(f"  ✨ User ID {uid}: *+{winnings}* မှတ် (သူ့စာရင်းအင်း ရှာမတွေ့ဘူးဗျို့!)") # Translated points and Stats not found
        result_message_text += "\n".join(payout_lines)
    else:
        result_message_text += "  ဒီတစ်ခါ ဘယ်သူမှ မနိုင်ခဲ့ပါဘူးဗျို့! 💔 နောက်တစ်ကြိမ် ကံကောင်းပါစေလို့ ဆုတောင်းပေးပါတယ်!"

    lost_players = []
    for uid in game.participants:
        if uid not in individual_payouts:
            # Use stats for player info
            player_info = stats.get(uid)
            if player_info:
                username_display = player_info['username'].replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
                lost_players.append(f"  💀 @{username_display} (ရမှတ်: *{player_info['score']}*)") # Translated Score
            else:
                lost_players.append(f"  💀 User ID {uid} (ရမှတ်ရှာမတွေ့ဘူးဗျို့!)") # Translated Score not found

    if lost_players:
        result_message_text += "\n\n*ကံစမ်းခဲ့သူများ (ဒါပေမဲ့ ဒီတစ်ခါတော့ ကံမကောင်းခဲ့သူများ):*\n"
        result_message_text += "\n".join(lost_players)


    try:
        logger.info(f"roll_and_announce_scheduled: Attempting to send 'Results' message for match {game.match_id} to chat {chat_id}.")
        await context.bot.send_message(chat_id, result_message_text, parse_mode="Markdown")
        logger.info(f"roll_and_announce_scheduled: 'Results' message sent successfully for match {game.match_id}.")
    except Exception as e:
        logger.error(f"roll_and_announce_scheduled: Error sending 'Results' message for chat {chat_id}: {e}", exc_info=True)

    # Access sequence state from context.chat_data[chat_id]
    chat_specific_context = context.chat_data.get(chat_id, {})
    if chat_specific_context.get("num_matches_total") is not None:
        logger.info(f"roll_and_announce_scheduled: Multi-match sequence active. Scheduling next game in sequence for chat {chat_id}.")
        # Store job for potential cancellation
        next_sequence_job = context.job_queue.run_once(
            _manage_game_sequence,
            5, # 5-second delay before starting the next game
            chat_id=chat_id,
            name=f"manage_sequence_{chat_id}_{chat_specific_context.get('current_match_index', 'final')}"
        )
        chat_specific_context["sequence_job"] = next_sequence_job # Update sequence job reference
    else:
        if "game" in chat_specific_context:
            del chat_specific_context["game"]
            logger.info(f"roll_and_announce_scheduled: Cleaned up game data for chat {chat_id} after single interactive match {game.match_id}.")

    logger.info(f"roll_and_announce_scheduled: Function finished for match {game.match_id} in chat {chat_id}.")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles inline keyboard button presses for placing bets.
    """
    query = update.callback_query
    # --- IMPORTANT FIX: Answer the callback query immediately to avoid "Query is too old" errors ---
    await query.answer() 
    # --- END FIX ---

    chat_id = update.effective_chat.id
    # --- Group ID check ---
    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"button_callback: Ignoring callback from disallowed chat ID: {chat_id}")
        # The answer() has already been sent, so we just return.
        return
    # --- END Group ID check ---
    
    data = query.data
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name
    
    # Escape markdown characters in username for display
    username_escaped = username.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')

    # Access game instance from context.chat_data[chat_id]
    chat_specific_context = context.chat_data.setdefault(chat_id, {})
    game = chat_specific_context.get("game")
    
    if not game:
        logger.info(f"button_callback: User {user_id} ({username}) tried to bet via button but no game active in chat {chat_id}.")
        return await query.message.reply_text(
            f"⚠️ @{username_escaped} ရေ၊ အန်စာတုံးဂိမ်းက မစရသေးပါဘူးဗျို့။ Admin တစ်ယောက်က /startdice နဲ့ ဂိမ်းစဖို့ လိုပါတယ်နော်။", 
            parse_mode="Markdown"
        )
    
    if game.state != WAITING_FOR_BETS:
        logger.info(f"button_callback: User {user_id} ({username}) tried to bet via button but betting is closed for match {game.match_id} in chat {chat_id}. State: {game.state}")
        return await query.message.reply_text(
            f"⚠️ @{username_escaped} ရေ၊ ဒီဂိမ်းအတွက် လောင်းကြေးတွေ ပိတ်သွားပြီနော်။ နောက်ပွဲကျမှ ပြန်လာခဲ့ပါ!", 
            parse_mode="Markdown"
        )

    bet_type = data.split("_")[1]
    
    # Call synchronous place_bet on game instance with chat_id
    success, response_message = game.place_bet(user_id, username, bet_type, 100, chat_id)
    
    await query.message.reply_text(response_message, parse_mode="Markdown")
    logger.info(f"button_callback: User {user_id} placed bet via button: {bet_type} (100 pts) in chat {chat_id}. Success: {success}")


async def handle_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles text-based bet commands (e.g., 'b 500', 's 200', 'l 100', 'big 50', 'lucky50').
    It now expects a single bet per message and will not be chatty on non-bet text.
    """
    chat_id = update.effective_chat.id
    # --- Group ID check ---
    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"handle_bet: Ignoring message from disallowed chat ID: {chat_id}")
        return # Do not send a reply to disallowed groups for non-command messages
    # --- END Group ID check ---

    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    message_text = update.message.text.strip()
    
    username_escaped = username.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')

    logger.info(f"handle_bet: User {user_id} ({username}) attempting to place text bet: '{message_text}' in chat {chat_id}")

    # Access game instance from context.chat_data[chat_id]
    chat_specific_context = context.chat_data.setdefault(chat_id, {})
    game = chat_specific_context.get("game")

    if not game:
        logger.info(f"handle_bet: User {user_id} tried to place text bet but no game active in chat {chat_id}.")
        return await update.message.reply_text(
            f"⚠️ @{username_escaped} ရေ၊ အန်စာတုံးဂိမ်းက မစရသေးပါဘူးဗျို့။ Admin တစ်ယောက်က /startdice နဲ့ ဂိမ်းစဖို့ လိုပါတယ်နော်။", 
            parse_mode="Markdown"
        )
    
    if game.state != WAITING_FOR_BETS:
        logger.info(f"handle_bet: User {user_id} ({username}) tried to place text bet but betting is closed for match {game.match_id} in chat {chat_id}. State: {game.state}")
        return await update.message.reply_text(
            f"⚠️ @{username_escaped} ရေ၊ ဒီဂိမ်းအတွက် လောင်းကြေးတွေ ပိတ်သွားပြီနော်။ နောက်ပွဲကျမှ ပြန်လာခဲ့ပါ!", 
            parse_mode="Markdown"
        )

    # Simplified regex for single bet parsing
    bet_match = re.match(r"^(big|b|small|s|lucky|l)\s*(\d+)$", message_text, re.IGNORECASE)

    if not bet_match:
        logger.warning(f"handle_bet: Invalid bet format for user {user_id} in message: '{message_text}' in chat {chat_id}.")
        return await update.message.reply_text(
            f"❌ @{username_escaped} ရေ၊ လောင်းကြေးပုံစံက မှားနေတယ်ဗျို့။ `big 500`၊ `small 100`၊ `lucky 250` လိုမျိုး ရိုက်ပေးပါနော်။\n"
            "ခလုတ်လေးတွေနှိပ်ပြီး လောင်းတာက ပိုလွယ်ပါတယ် (မူရင်း ၁၀၀ မှတ်နော်)။",
            parse_mode="Markdown"
        )
    
    bet_type_str, amount_str = bet_match.groups()
    
    bet_types_map = {
        "b": "big", "big": "big",
        "s": "small", "small": "small",
        "l": "lucky", "lucky": "lucky"
    }
    bet_type = bet_types_map.get(bet_type_str.lower())
    
    try:
        amount = int(amount_str)
    except ValueError:
        logger.error(f"handle_bet: Failed to convert bet amount to integer from user {user_id}: '{amount_str}' in chat {chat_id}.")
        # This error should ideally be caught by the regex already (digits only)
        return await update.message.reply_text(f"❌ @{username_escaped} ရေ၊ လောင်းကြေးပမာဏက ဂဏန်းဖြစ်ရပါမယ်ဗျို့။", parse_mode="Markdown")

    # Call synchronous place_bet on game instance with chat_id
    success, msg = game.place_bet(user_id, username, bet_type, amount, chat_id)
    
    await update.message.reply_text(msg, parse_mode="Markdown")
    logger.info(f"handle_bet: User {user_id} placed bet: {bet_type} {amount} pts in chat {chat_id}. Success: {success}")


async def show_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Displays the user's current points, total wins, and total losses.
    """
    chat_id = update.effective_chat.id
    # --- Group ID check ---
    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"show_score: Ignoring command from disallowed chat ID: {chat_id}")
        await update.message.reply_text(f"ဆောရီးနော်၊ ကျွန်တော်က ဒီ group ({chat_id}) မှာ ကစားဖို့ ခွင့်ပြုချက်မရှိပါဘူး။ ခွင့်ပြုထားတဲ့ group ထဲ ထည့်ပေးပါဦးနော်။", parse_mode="Markdown")
        return
    # --- END Group ID check ---

    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    logger.info(f"show_score: User {user_id} ({username}) requested score in chat {chat_id}")

    # Fetch player stats from in-memory global_data
    chat_specific_data = get_chat_data_for_id(chat_id)
    player_stats = chat_specific_data["player_stats"].get(user_id)

    if player_stats:
        await update.message.reply_text(
            f"📊 @{username.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')} ရေ၊ သင့်လက်ထဲမှာ *{player_stats['score']}* မှတ်တောင် ရှိနေပြီနော်!\n" 
            f"✅ အနိုင်ရမှု: *{player_stats['wins']}* ပွဲ | ❌ ရှုံးနိမ့်မှု: *{player_stats['losses']}* ပွဲ", 
            parse_mode="Markdown"
        )
    else:
        # This case should be rare now with auto-initialization in place_bet, but kept as a fallback.
        await update.message.reply_text(
            "ℹ️ ဒီ chat မှာ ဂိမ်းတွေ မကစားရသေးဘူးဗျို့။ Admin တစ်ယောက်ကို /startdice နဲ့ စတင်ခိုင်းပြီး အမှတ်တွေ စုလိုက်တော့နော်!",
            parse_mode="Markdown"
        )

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Displays detailed personal game statistics for the user,
    including points, games played, wins, losses, win rate, and last active time.
    """
    chat_id = update.effective_chat.id
    # --- Group ID check ---
    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"show_stats: Ignoring command from disallowed chat ID: {chat_id}")
        await update.message.reply_text(f"ဆောရီးနော်၊ ကျွန်တော်က ဒီ group ({chat_id}) မှာ ကစားဖို့ ခွင့်ပြုချက်မရှိပါဘူး။ ခွင့်ပြုထားတဲ့ group ထဲ ထည့်ပေးပါဦးနော်။", parse_mode="Markdown")
        return
    # --- END Group ID check ---

    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    logger.info(f"show_stats: User {user_id} ({username}) requested detailed stats in chat {chat_id}")

    # Fetch player stats from in-memory global_data
    chat_specific_data = get_chat_data_for_id(chat_id)
    player_stats = chat_specific_data["player_stats"].get(user_id)

    if player_stats:
        total_games = player_stats['wins'] + player_stats['losses']
        win_rate = 0.0 
        if total_games > 0:
            win_rate = (player_stats['wins'] / total_games) * 100

        username_display = player_stats['username'].replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')

        await update.message.reply_text(
            f"👤 *@{username_display}* ရဲ့ ဂိမ်းစာရင်းအင်း အစုံအလင်: \n" 
            f"  လက်ရှိရမှတ်: *{player_stats['score']}*\n" 
            f"  စုစုပေါင်း ကစားခဲ့တဲ့ပွဲ: *{total_games}* ပွဲ\n" 
            f"  ✅ အနိုင်ရမှု: *{player_stats['wins']}* ပွဲ\n" 
            f"  ❌ ရှုံးနိမ့်မှု: *{player_stats['losses']}* ပွဲ\n" 
            f"  နိုင်တဲ့နှုန်းထား: *{win_rate:.1f}%*\n" 
            f"  နောက်ဆုံးလှုပ်ရှားခဲ့တဲ့အချိန်: *{player_stats['last_active'].strftime('%Y-%m-%d %H:%M')}*", 
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("ℹ️ စာရင်းအင်းတွေ မရှိသေးဘူးဗျို့။ ဂိမ်းစကစားပြီး အမှတ်တွေ စုလိုက်တော့နော်!", parse_mode="Markdown")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Displays the top 10 players by score in the current chat.
    Filters out players who haven't made any bets (still on initial 1000 points).
    """
    chat_id = update.effective_chat.id
    # --- Group ID check ---
    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"leaderboard: Ignoring command from disallowed chat ID: {chat_id}")
        await update.message.reply_text(f"ဆောရီးနော်၊ ကျွန်တော်က ဒီ group ({chat_id}) မှာ ကစားဖို့ ခွင့်ပြုချက်မရှိပါဘူး။ ခွင့်ပြုထားတဲ့ group ထဲ ထည့်ပေးပါဦးနော်။", parse_mode="Markdown")
        return
    # --- END Group ID check ---

    logger.info(f"leaderboard: User {update.effective_user.id} requested leaderboard in chat {chat_id}")

    # Fetch all player stats from in-memory global_data
    chat_specific_data = get_chat_data_for_id(chat_id)
    stats_for_chat = chat_specific_data["player_stats"]
    all_players_stats = list(stats_for_chat.values()) # Convert dict_values to list
    
    active_players = [
        p for p in all_players_stats
        if p["wins"] > 0 or p["losses"] > 0 or p["score"] != INITIAL_PLAYER_SCORE
    ]
    # Sort by score
    top_players = sorted(active_players, key=lambda x: x["score"], reverse=True)[:10]

    if not top_players:
        return await update.message.reply_text("ℹ️ ဒီ chat မှာ မှတ်တမ်းတင်ထားတဲ့ ကစားသမားတွေ မရှိသေးဘူးဗျို့။ ဂိမ်းစကစားပြီး လောင်းကြေးထပ်လိုက်နော်!", parse_mode="Markdown")
    
    message_lines = ["🏆 *ဒီ group ရဲ့ ထိပ်တန်း ကစားသမားအချမ်းသာဆုံးများ:*\n"]
    for i, player in enumerate(top_players):
        username_display = player['username'].replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
        message_lines.append(f"{i+1}. @{username_display}: *{player['score']}* မှတ်") 
    
    await update.message.reply_text("\n".join(message_lines), parse_mode="Markdown")


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Displays the recent match history for the current chat (last 5 matches).
    """
    chat_id = update.effective_chat.id
    # --- Group ID check ---
    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"history: Ignoring command from disallowed chat ID: {chat_id}")
        await update.message.reply_text(f"ဆောရီးနော်၊ ကျွန်တော်က ဒီ group ({chat_id}) မှာ ကစားဖို့ ခွင့်ပြုချက်မရှိပါဘူး။ ခွင့်ပြုထားတဲ့ group ထဲ ထည့်ပေးပါဦးနော်။", parse_mode="Markdown")
        return
    # --- END Group ID check ---

    logger.info(f"history: User {update.effective_user.id} requested match history in chat {chat_id}")

    # Fetch match history from in-memory global_data
    chat_specific_data = get_chat_data_for_id(chat_id)
    match_history_for_chat = chat_specific_data["match_history"]
    
    # Take last 5 and reverse to show newest at the top of the displayed list
    recent_matches = match_history_for_chat[-5:][::-1]
    
    if not recent_matches: # Changed from match_history_for_chat to recent_matches
        return await update.message.reply_text("ℹ️ ဒီ chat မှာ ပွဲမှတ်တမ်းတွေ မရှိသေးဘူးဗျို့။ မှတ်တမ်းတွေ ရှိလာအောင် ဂိမ်းတွေ စကစားလိုက်နော်!", parse_mode="Markdown")
    
    message_lines = ["📜 *မကြာသေးခင်က ပြီးဆုံးသွားတဲ့ ပွဲစဉ်တွေ (နောက်ဆုံး ၅ ပွဲ):*\n"]
    for match in recent_matches: # Changed to recent_matches
        timestamp_str = match['timestamp'].strftime('%Y-%m-%d %H:%M')
        winner_display = match['winner'].upper().replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
        winner_emoji = RESULT_EMOJIS.get(match['winner'], '')
        
        message_lines.append(
            f"  • ပွဲစဉ် #{match['match_id']} | ရလဒ်: *{match['result']}* ({winner_display} {winner_emoji}) | ပါဝင်သူ: *{match['participants']}* ဦး | အချိန်: {timestamp_str}" 
        )
    
    await update.message.reply_text("\n".join(message_lines), parse_mode="Markdown")

async def adjust_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Admin command to adjust a player's score.
    Usage:
    - Reply to a user's message: /adjustscore <amount>
    - Direct input (numeric ID): /adjustscore <user_id> <amount>
    - Direct input (@username): /adjustscore @username <amount>
    """
    chat_id = update.effective_chat.id
    # --- Group ID check ---
    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"adjust_score: Ignoring command from disallowed chat ID: {chat_id}")
        await update.message.reply_text(f"ဆောရီးနော်၊ ကျွန်တော်က ဒီ group ({chat_id}) မှာ ကစားဖို့ ခွင့်ပြုချက်မရှိပါဘူး။ ခွင့်ပြုထားတဲ့ group ထဲ ထည့်ပေးပါဦးနော်။", parse_mode="Markdown")
        return
    # --- END Group ID check ---

    requester_user_id = update.effective_user.id
    logger.info(f"adjust_score: User {requester_user_id} attempting to adjust score in chat {chat_id}")

    if not is_admin(chat_id, requester_user_id):
        logger.warning(f"adjust_score: User {requester_user_id} is not an admin and tried to adjust score in chat {chat_id}.")
        return await update.message.reply_text("❌ Admin တွေပဲ ကစားသမားရမှတ်တွေကို ချိန်ညှိခွင့်ရှိတယ်နော်။", parse_mode="Markdown")

    target_user_id = None
    amount_to_adjust = None
    target_username_display = None

    chat_specific_data = get_chat_data_for_id(chat_id)
    player_stats_for_chat = chat_specific_data["player_stats"]

    if update.message.reply_to_message:
        if not context.args or len(context.args) != 1:
            return await update.message.reply_text(
                "❌ ပြန်ဖြေရာမှာ အသုံးပြုပုံ မှားနေတယ်နော်။ ကျေးဇူးပြုပြီး: `/adjustscore <ပမာဏ>` လို့ ရိုက်ပေးပါဦး။\n"
                "ဥပမာ- ကစားသမားတစ်ယောက်ရဲ့ မက်ဆေ့ချ်ကို Reply လုပ်ပြီး `/adjustscore 500` (အမှတ် ၅၀၀ ထည့်ရန်) လို့ ရိုက်ပါ။",
                parse_mode="Markdown"
            )
        
        target_user_id = update.message.reply_to_message.from_user.id
        target_username_display = update.message.reply_to_message.from_user.username or update.message.reply_to_message.from_user.first_name
        
        try:
            amount_to_adjust = int(context.args[0])
        except ValueError:
            return await update.message.reply_text(
                "❌ ပမာဏက ဂဏန်းဖြစ်ရပါမယ်နော်။ သေချာစစ်ပေးပါ။\n"
                "ဥပမာ- ကစားသမားတစ်ယောက်ရဲ့ မက်ဆေ့ချ်ကို Reply လုပ်ပြီး `/adjustscore 500` လို့ ရိုက်ပါ။",
                parse_mode="Markdown"
            )

    elif context.args and len(context.args) >= 2:
        first_arg = context.args[0]
        try:
            amount_to_adjust = int(context.args[1])
        except ValueError:
            return await update.message.reply_text(
                "❌ ပမာဏက ဂဏန်းဖြစ်ရပါမယ်နော်။ သေချာစစ်ပေးပါ။\n"
                "ဥပမာ- `/adjustscore 123456789 500` ဒါမှမဟုတ် `/adjustscore @someuser 100`။",
                parse_mode="Markdown"
            )
        
        if first_arg.startswith('@'):
            mentioned_username = first_arg[1:]
            
            # Search in-memory player_stats for username
            for uid, player_info in player_stats_for_chat.items():
                if player_info.get("username", "").lower() == mentioned_username.lower():
                    target_user_id = uid
                    target_username_display = player_info.get("username")
                    break
            
            if target_user_id is None: # User not found in local player_stats by username
                return await update.message.reply_text(
                    f"❌ အသုံးပြုသူ '@{mentioned_username}' ကို ဒီ chat ရဲ့ ဂိမ်းဒေတာထဲမှာ ရှာမတွေ့ဘူးဗျို့။ သူတို့က ဒီ bot နဲ့ ဒီ chat ထဲမှာ တစ်ခါမှ မကစားဖူးသေးတာ ဖြစ်နိုင်တယ်။ သူတို့ရဲ့ မက်ဆေ့ချ်တစ်ခုခုကို Reply လုပ်ကြည့်ပါ ဒါမှမဟုတ် သူတို့ရဲ့ User ID ဂဏန်းကို သုံးကြည့်ပါနော်။",
                    parse_mode="Markdown"
                )
        else: # Numeric user ID provided
            try:
                target_user_id = int(first_arg)
            except ValueError:
                return await update.message.reply_text(
                    "❌ User ID (သို့) ပမာဏက မှားနေတယ်နော်။ ကျေးဇူးပြုပြီး: `/adjustscore <user_id> <ပမာဏ>` ဒါမှမဟုတ် `/adjustscore @username <ပမာဏ>` ကိုသုံးပါ။\n"
                    "ဥပမာ- `/adjustscore 123456789 500` ဒါမှမဟုတ် `/adjustscore @someuser 100`။",
                    parse_mode="Markdown"
                )
            
    else: # Neither reply nor valid direct args
        return await update.message.reply_text(
            "❌ အသုံးပြုပုံ မှားနေတယ်နော်။ အောက်ပါတို့မှ တစ်ခုကို သုံးကြည့်ပါ:\n"
            "  - ကစားသမားရဲ့ မက်ဆေ့ချ်ကို Reply လုပ်ပြီး: `/adjustscore <ပမာဏ>`\n"
            "  - တိုက်ရိုက် ရိုက်ထည့်: `/adjustscore <user_id> <ပမာဏ>`\n"
            "  - ဒါမှမဟုတ်: `/adjustscore @username <ပမာဏ>`\n"
            "ဥပမာ- `/adjustscore 123456789 500` ဒါမှမဟုတ် `/adjustscore @someuser 100`။",
            parse_mode="Markdown"
        )

    if target_user_id is None or amount_to_adjust is None:
        logger.error(f"adjust_score: Logic error: target_user_id ({target_user_id}) or amount_to_adjust ({amount_to_adjust}) is None after initial parsing. update_message: {update.message.text}")
        return await update.message.reply_text("❌ မထင်မှတ်ထားတဲ့ အမှားလေးတစ်ခု ဖြစ်သွားတယ်ဗျို့။ ထပ်ကြိုးစားကြည့်ပါဦးနော်။", parse_mode="Markdown")

    # Directly access and update in-memory player_stats
    target_player_stats = player_stats_for_chat.setdefault(target_user_id, { # Use setdefault to ensure it exists
            "username": target_username_display or f"User {target_user_id}", # Initialize username if not found
            "score": INITIAL_PLAYER_SCORE,
            "wins": 0,
            "losses": 0,
            "last_active": datetime.now()
        })

    if not target_player_stats: # This check might be redundant if setdefault works as expected
        try:
            chat_member = await context.bot.get_chat_member(chat_id, target_user_id)
            fetched_username = chat_member.user.username or chat_member.user.first_name
            
            player_stats_for_chat[target_user_id] = {
                "username": fetched_username,
                "score": INITIAL_PLAYER_SCORE,
                "wins": 0,
                "losses": 0,
                "last_active": datetime.now()
            }
            target_player_stats = player_stats_for_chat[target_user_id]
            if target_username_display is None:
                target_username_display = fetched_username 
        except Exception as e:
            logger.error(f"adjust_score: Failed to fetch user details for {target_user_id} in chat {chat_id}: {e}", exc_info=True)
            return await update.message.reply_text(
                f"❌ User ID `{target_user_id}` ရှိ ကစားသမားကို ဒီ chat မှာ ရှာမတွေ့ဘူးဗျို့။ Telegram က အသေးစိတ်အချက်အလက်တွေ ရယူလို့ မရတာ ဖြစ်နိုင်တယ်။ သူတို့က ဒီ group ထဲမှာ ရှိလား ဒါမှမဟုတ် သူတို့ရဲ့ မက်ဆေ့ချ်တစ်ခုကို Reply လုပ်ကြည့်ပါဦးနော်။",
                parse_mode="Markdown"
            )
            
    if target_username_display is None:
        target_username_display = target_player_stats.get('username', f"User {target_user_id}")

    old_score = target_player_stats['score']
    target_player_stats['score'] += amount_to_adjust
    target_player_stats['last_active'] = datetime.now() 
    new_score_val = target_player_stats['score'] # Use new_score_val for display consistent with prior Firebase attempt
    # Ensure username is up-to-date
    target_player_stats['username'] = target_username_display
    

    username_display_escaped = target_username_display.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')

    await update.message.reply_text(
        f"✅ *@{username_display_escaped}* (အိုင်ဒီ: `{target_user_id}`) ရဲ့ ရမှတ်ကို *{amount_to_adjust}* မှတ် ချိန်ညှိပေးလိုက်ပါပြီဗျို့။\n" 
        f"အရင်ရမှတ်: *{old_score}* | အခုရမှတ်အသစ်: *{new_score_val}*။ (ကဲ... အမှတ်တိုးပြီပေါ့! 😉)",
        parse_mode="Markdown"
    )
    logger.info(f"adjust_score: User {requester_user_id} adjusted score for {target_user_id} in chat {chat_id} by {amount_to_adjust}. New score: {new_score_val}")

async def check_user_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Admin command to check a specific player's score and stats.
    Usage:
    - Reply to a user's message: /checkscore
    - Direct input (numeric ID): /checkscore <user_id>
    - Direct input (@username): /checkscore @username
    """
    chat_id = update.effective_chat.id
    # --- Group ID check ---
    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"check_user_score: Ignoring command from disallowed chat ID: {chat_id}")
        await update.message.reply_text(f"ဆောရီးနော်၊ ကျွန်တော်က ဒီ group ({chat_id}) မှာ ကစားဖို့ ခွင့်ပြုချက်မရှိပါဘူး။ ခွင့်ပြုထားတဲ့ group ထဲ ထည့်ပေးပါဦးနော်။", parse_mode="Markdown")
        return
    # --- END Group ID check ---

    requester_user_id = update.effective_user.id
    logger.info(f"check_user_score: User {requester_user_id} attempting to check score in chat {chat_id}")

    if not is_admin(chat_id, requester_user_id):
        logger.warning(f"check_user_score: User {requester_user_id} is not an admin and tried to check score in chat {chat_id}.")
        return await update.message.reply_text("❌ Admin တွေပဲ တခြားကစားသမားတွေရဲ့ ရမှတ်တွေကို စစ်ဆေးခွင့်ရှိတယ်နော်။", parse_mode="Markdown")

    target_user_id = None
    target_username_display = None

    chat_specific_data = get_chat_data_for_id(chat_id)
    player_stats_for_chat = chat_specific_data["player_stats"]

    if update.message.reply_to_message:
        target_user_id = update.message.reply_to_message.from_user.id
        target_username_display = update.message.reply_to_message.from_user.username or update.message.reply_to_message.from_user.first_name
        logger.info(f"check_user_score: Admin {requester_user_id} checking score by reply for user {target_user_id}.")
    elif context.args and len(context.args) == 1:
        first_arg = context.args[0]
        
        if first_arg.startswith('@'):
            mentioned_username = first_arg[1:]
            
            # Search in-memory player_stats for username
            for uid, player_info in player_stats_for_chat.items():
                if player_info.get("username", "").lower() == mentioned_username.lower():
                    target_user_id = uid
                    target_username_display = player_info.get("username")
                    break
            
            if target_user_id is None: # User not found in local player_stats by username
                return await update.message.reply_text(
                    f"❌ အသုံးပြုသူ '@{mentioned_username}' ကို ဒီ chat ရဲ့ ဂိမ်းဒေတာထဲမှာ ရှာမတွေ့ဘူးဗျို့။ သူတို့က ဒီ bot နဲ့ ဒီ chat ထဲမှာ တစ်ခါမှ မကစားဖူးသေးတာ ဖြစ်နိုင်တယ်။ သူတို့ရဲ့ မက်ဆေ့ချ်တစ်ခုခုကို Reply လုပ်ကြည့်ပါ ဒါမှမဟုတ် သူတို့ရဲ့ User ID ဂဏန်းကို သုံးကြည့်ပါနော်။",
                    parse_mode="Markdown"
                )
        else: # Numeric user ID provided
            try:
                target_user_id = int(first_arg)
                logger.info(f"check_user_score: Admin {requester_user_id} checking score by numeric ID for user {target_user_id}.")
            except ValueError:
                return await update.message.reply_text(
                    "❌ User ID (သို့) ပမာဏက မှားနေတယ်နော်။ ကျေးဇူပြု၍: `/checkscore <user_id>` ဒါမှမဟုတ် `/checkscore @username` ကိုသုံးပါ။\n"
                    "ဥပမာ- `/checkscore 123456789` ဒါမှမဟုတ် `/checkscore @someuser`။",
                    parse_mode="Markdown"
                )
    else:
        return await update.message.reply_text(
            "❌ အသုံးပြုပုံ မှားနေတယ်နော်။ ကျေးဇူပြု၍ အောက်ပါတို့မှ တစ်ခုကို သုံးကြည့်ပါ:\n"
            "  - ကစားသမားရဲ့ မက်ဆေ့ချ်ကို Reply လုပ်ပြီး: `/checkscore`\n"
            "  - တိုက်ရိုက် ရိုက်ထည့်: `/checkscore <user_id>`\n"
            "  - ဒါမှမဟုတ်: `/checkscore @username`\n"
            "ဥပမာ- `/checkscore 123456789` ဒါမှမဟုတ် `/checkscore @someuser`။",
            parse_mode="Markdown"
        )

    if target_user_id is None:
        logger.error(f"check_user_score: Logic error: target_user_id ({target_user_id}) is None after initial parsing. update_message: {update.message.text}")
        return await update.message.reply_text("❌ မထင်မှတ်ထားတဲ့ အမှားလေးတစ်ခု ဖြစ်သွားတယ်ဗျို့။ ထပ်ကြိုးစားကြည့်ပါဦးနော်။", parse_mode="Markdown")

    # Fetch player stats from in-memory global_data for display
    player_stats = player_stats_for_chat.get(target_user_id)

    if not player_stats:
        try:
            chat_member = await context.bot.get_chat_member(chat_id, target_user_id)
            fetched_username = chat_member.user.username or chat_member.user.first_name
            username_display_escaped = fetched_username.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
            
            await update.message.reply_text(
                f"👤 *@{username_display_escaped}* (အိုင်ဒီ: `{target_user_id}`) အတွက် ဒီ chat မှာ ဂိမ်းစာရင်းအင်းတွေ မရှိသေးဘူးဗျို့။\n"
                f"သူတို့ရဲ့ လက်ရှိရမှတ်ကတော့ အစကတည်းက ပေးထားတဲ့ *{INITIAL_PLAYER_SCORE}* မှတ်ပဲ ရှိပါသေးတယ်။",
                parse_mode="Markdown"
            )
            logger.info(f"check_user_score: Admin {requester_user_id} checked score for new user {target_user_id} (no stats yet).")
            return # Exit after informing user

        except Exception as e:
            logger.error(f"check_user_score: Failed to find player {target_user_id} or fetch their details in chat {chat_id}: {e}", exc_info=True)
            return await update.message.reply_text(
                f"❌ User ID `{target_user_id}` ရှိ ကစားသမားကို ဒီ chat မှာ ရှာမတွေ့ဘူးဗျို့။ Telegram က အသေးစိတ်အချက်အလက်တွေ ရယူလို့ မရတာ ဖြစ်နိုင်တယ်။ သူတို့က ဒီ group ထဲမှာ ရှိလား ဒါမှမဟုတ် သူတို့ရဲ့ မက်ဆေ့ချ်တစ်ခုကို Reply လုပ်ကြည့်ပါဦးနော်။",
                parse_mode="Markdown"
            )
            
    if target_username_display is None:
        target_username_display = player_stats.get('username', f"User {target_user_id}")
    
    # Rest of the check_user_score logic (displaying stats)
    total_games = player_stats['wins'] + player_stats['losses']
    win_rate = 0.0
    if total_games > 0:
        win_rate = (player_stats['wins'] / total_games) * 100

    username_display_escaped = target_username_display.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')

    await update.message.reply_text(
        f"👤 *@{username_display_escaped}* ရဲ့ ဂိမ်းစာရင်းအင်း အစုံအလင် (အိုင်ဒီ: `{target_user_id}`):\n"
        f"  လက်ရှိရမှတ်: *{player_stats['score']}*\n"
        f"  စုစုပေါင်း ကစားခဲ့တဲ့ပွဲ: *{total_games}* ပွဲ\n"
        f"  ✅ အနိုင်ရမှု: *{player_stats['wins']}* ပွဲ\n"
        f"  ❌ ရှုံးနိမ့်မှု: *{player_stats['losses']}* ပွဲ\n"
        f"  နိုင်တဲ့နှုန်းထား: *{win_rate:.1f}%*\n"
        f"  နောက်ဆုံးလှုပ်ရှားခဲ့တဲ့အချိန်: *{player_stats['last_active'].strftime('%Y-%m-%d %H:%M')}*",
        parse_mode="Markdown"
    )
    logger.info(f"check_user_score: Admin {requester_user_id} successfully checked score for user {target_user_id}.")

async def refresh_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Admin command to force a refresh of the group's admin list.
    """
    chat_id = update.effective_chat.id
    # --- Group ID check ---
    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"refresh_admins: Ignoring command from disallowed chat ID: {chat_id}")
        await update.message.reply_text(f"ဆောရီးနော်၊ ကျွန်တော်က ဒီ group ({chat_id}) မှာ ကစားဖို့ ခွင့်ပြုချက်မရှိပါဘူး။ ခွင့်ပြုထားတဲ့ group ထဲ ထည့်ပေးပါဦးနော်။", parse_mode="Markdown")
        return
    # --- END Group ID check ---

    user_id = update.effective_user.id

    # Allow hardcoded global admins to use this even if group_admins isn't yet populated
    if not is_admin(chat_id, user_id) and user_id not in HARDCODED_ADMINS:
        logger.warning(f"refresh_admins: User {user_id} tried to refresh admins in chat {chat_id} but is not an admin.")
        return await update.message.reply_text("❌ Admin တွေပဲ အုပ်ချုပ်သူစာရင်းကို အသစ်ပြန်တင်လို့ရပါတယ်နော်။", parse_mode="Markdown")

    logger.info(f"refresh_admins: User {user_id} attempting to refresh admin list for chat {chat_id}.")
    
    if await update_group_admins(chat_id, context):
        await update.message.reply_text("✅ အုပ်ချုပ်သူစာရင်းကို အောင်မြင်စွာ အသစ်ပြန်တင်ပြီးပါပြီ! ကဲ... ဘယ်သူတွေ ထပ်ပါလာလဲ ကြည့်လိုက်ဦးနော်။", parse_mode="Markdown")
    else:
        await update.message.reply_text(
            "❌ အုပ်ချုပ်သူစာရင်းကို အသစ်ပြန်တင်လို့မရပါဘူးဗျို့။ ကျွန်တော့်ကို 'ချတ်အုပ်ချုပ်သူများကို ရယူရန်' ခွင့်ပြုချက် ပေးထားလား သေချာစစ်ပေးပါဦးနော်။",
            parse_mode="Markdown"
        )


async def stop_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Admin command to stop the current game and refund all placed bets.
    """
    chat_id = update.effective_chat.id

    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"stop_game: Ignoring command from disallowed chat ID: {chat_id}")
        await update.message.reply_text(f"ဆောရီးနော်၊ ကျွန်တော်က ဒီ group ({chat_id}) မှာ ကစားဖို့ ခွင့်ပြုချက်မရှိပါဘူး။ ခွင့်ပြုထားတဲ့ group ထဲ ထည့်ပေးပါဦးနော်။", parse_mode="Markdown")
        return

    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    logger.info(f"stop_game: User {user_id} ({username}) attempting to stop a game in chat {chat_id}")

    if not is_admin(chat_id, user_id):
        logger.warning(f"stop_game: User {user_id} is not an admin and tried to stop a game in chat {chat_id}.")
        return await update.message.reply_text("❌ Admin တွေပဲ လက်ရှိဂိမ်းကို ရပ်တန့်လို့ရပါတယ်နော်။", parse_mode="Markdown")

    chat_specific_context = context.chat_data.setdefault(chat_id, {})
    current_game = chat_specific_context.get("game")

    if not current_game or current_game.state == GAME_OVER:
        logger.info(f"stop_game: No active game to stop in chat {chat_id}.")
        return await update.message.reply_text("ℹ️ ဟေး! လက်ရှိစတင်ထားတဲ့ အန်စာတုံးဂိမ်း မရှိသေးဘူးဗျို့။ ရပ်ဖို့လည်း မလိုဘူးပေါ့!", parse_mode="Markdown")

    # Cancel any pending jobs related to this game instance
    jobs_to_cancel = [
        chat_specific_context.get("close_bets_job"),
        chat_specific_context.get("roll_and_announce_job"),
        chat_specific_context.get("sequence_job"), # For multi-match sequences
        chat_specific_context.get("next_game_job") # For the next game in a sequence
    ]
    
    for job in jobs_to_cancel:
        if job and job.running: # Check if job exists and is still running
            job.schedule_removal()
            logger.info(f"stop_game: Canceled job '{job.name}' for chat {chat_id}.")

    refunded_players_info = []
    player_stats_for_chat = get_chat_data_for_id(chat_id)["player_stats"]

    # Refund all bets
    total_refunded_amount = 0
    total_bets_by_user = {}

    for bet_type_dict in current_game.bets.values():
        for uid, amount_bet in bet_type_dict.items():
            total_bets_by_user[uid] = total_bets_by_user.get(uid, 0) + amount_bet
    
    for uid, refunded_amount in total_bets_by_user.items():
        if uid in player_stats_for_chat:
            player_stats = player_stats_for_chat[uid]
            player_stats["score"] += refunded_amount
            player_stats["last_active"] = datetime.now() # Update last active time
            total_refunded_amount += refunded_amount
            
            username_display = player_stats['username'].replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
            refunded_players_info.append(
                f"  @{username_display}: *+{refunded_amount}* မှတ် (အခုရမှတ်: *{player_stats['score']}*)"
            )
            logger.info(f"stop_game: Refunded {refunded_amount} to user {uid} in chat {chat_id}. New score: {player_stats['score']}")
        else:
            logger.warning(f"stop_game: Could not find player {uid} in stats for refund in chat {chat_id}.")

    # Clear the game instance from context.chat_data
    del chat_specific_context["game"]
    # Clear any sequence-related state if present
    if "num_matches_total" in chat_specific_context: del chat_specific_context["num_matches_total"]
    if "current_match_index" in chat_specific_context: del chat_specific_context["current_match_index"]
    # Also clean up the job references
    if "close_bets_job" in chat_specific_context: del chat_specific_context["close_bets_job"]
    if "roll_and_announce_job" in chat_specific_context: del chat_specific_context["roll_and_announce_job"]
    if "sequence_job" in chat_specific_context: del chat_specific_context["sequence_job"]
    if "next_game_job" in chat_specific_context: del chat_specific_context["next_game_job"]


    refund_message = f"🛑 *ပွဲစဉ် #{current_game.match_id} ကို ရပ်တန့်လိုက်ပါပြီဗျို့!* 🛑\n\n"
    if refunded_players_info:
        refund_message += "*လောင်းကြေးတွေ အားလုံး ပြန်အမ်းပေးလိုက်ပါပြီနော်:*\n"
        refund_message += "\n".join(refunded_players_info)
        refund_message += f"\n\nစုစုပေါင်း ပြန်အမ်းပေးလိုက်တဲ့အမှတ်: *{total_refunded_amount}* မှတ်။ (ကဲ... အမှတ်တွေ ပြန်ရပြီဆိုတော့ ပြုံးလိုက်တော့! 😊)"
    else:
        refund_message += "ဒီပွဲမှာ ဘယ်သူမှ မလောင်းထားတော့ ပြန်အမ်းစရာ မရှိဘူးဗျို့။"

    await update.message.reply_text(refund_message, parse_mode="Markdown")
    logger.info(f"stop_game: Match {current_game.match_id} successfully stopped and bets refunded in chat {chat_id}.")
