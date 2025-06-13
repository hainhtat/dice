import logging
import asyncio # For async.sleep
from datetime import datetime
import random # For random.randint fallback in dice roll
import re # Import the 're' module for regex operations
from typing import Optional # Import Optional for type hinting
from apscheduler.jobstores.base import JobLookupError # Import JobLookupError for error handling

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes # Only ContextTypes is needed here from telegram.ext

# Import necessary components from other modules
from game_logic import DiceGame, WAITING_FOR_BETS, GAME_CLOSED, GAME_OVER
from constants import global_data, HARDCODED_ADMINS, RESULT_EMOJIS, INITIAL_PLAYER_SCORE, ALLOWED_GROUP_IDS, get_chat_data_for_id


# Configure logging for this module (this will be overridden by main.py's config)
logger = logging.getLogger(__name__)


def is_admin(chat_id, user_id):
    """
    Checks if a user is an administrator in a specific chat
    or if they are one of the hardcoded global administrators.
    """
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
                    "🎉 *အန်စာတုံးဂိမ်း ကမ္ဘာလေးထဲကို ကြိုဆိုပါတယ်ရှင့်!* 🎉\n" # Feminine welcome
                    "ကဲ.. ကံစမ်းမလားဟင်? စွန့်စားခန်းတွေ စလိုက်ရအောင်! Admin တွေကတော့ /startdice နဲ့ ဂိမ်းစလို့ရတယ်။ ကစားသမားလေးတွေက ကိုယ့် /score ကို ကြည့်ပြီး လောင်းကြေးထပ်ဖို့ အသင့်ပြင်ထားနော်။ ကံကောင်းကြပါစေရှင့်! 😉", # Feminine, casual
                    parse_mode="Markdown"
                )
            else:
                await context.bot.send_message(
                    chat_id,
                    "👋 ဟိုင်း! ကျွန်တော်က အန်စာတုံးဂိမ်းဘော့တ်ပါ။ Admin စာရင်းကို ရယူရာမှာ နည်းနည်းအခက်အခဲရှိနေလို့ပါ။ 'Chat Admins တွေကို ရယူဖို့' ခွင့်ပြုချက် ပေးထားလား စစ်ပေးပါဦးနော်။", # More casual error
                    parse_mode="Markdown"
                )
        elif new_status == "left":
            logger.info(f"on_chat_member_update: Bot was removed from chat {chat_id}.")
            # Clean up all chat-specific data when the bot is removed from the group
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
        await update.message.reply_text(f"Sorry, this bot is not authorized to run in this group ({chat_id}). Please add it to an allowed group.", parse_mode="Markdown")
        return
    # --- END Group ID check ---

    user_id = update.effective_user.id
    logger.info(f"start: Received /start command from user {user_id} in chat {chat_id}")

    await update.message.reply_text(
        "🌟🎲 *အန်စာတုံးဂိမ်း ကမ္ဘာလေးထဲကို ကြိုဆိုပါတယ်ရှင့်!* 🎉🌟\n\n" # Feminine welcome
        "ကဲ.. ကံစမ်းမလားဟင်? စွန့်စားခန်းတွေ စလိုက်ရအောင်! ဂိမ်းစည်းမျဉ်းလေးတွေက ဒီလိုပါရှင့်:\n\n" # Feminine intro
        "✨ *ဂိမ်းစည်းမျဉ်းလေးတွေ:* အန်စာတုံး ၂ လုံးလှိမ့်မယ်နော်။ အဲ့ဒီရလဒ်ကို ခန့်မှန်းရမှာပေါ့!\n"
        "  - *BIG* 🔼: ၇ ထက်ကြီးတယ် (လောင်းတဲ့ပမာဏရဲ့ ၂ ဆ ပြန်ရမယ်နော်!)\n"
        "  - *SMALL* 🔽: ၇ ထက်ငယ်တယ် (ဒါလည်း ၂ ဆပဲ ပြန်ရမှာနော်!)\n"
        "  - *LUCKY* 🍀: ၇ အတိအကျ (ကဲ ဒါကတော့ ၅ ဆတောင် ပြန်ရမှာ!)\n\n"
        "💰 *ဘယ်လိုလောင်းမလဲ:*\n"
        "  - လောင်းကြေးထပ်ချိန် (မူရင်း ၁၀၀ မှတ်ပဲ ရှိသေးတယ်နော်) အတွင်း ခလုတ်လေးတွေကို နှိပ်ပြီး လောင်းလို့ရတယ်။\n"
        "  - ဒါမှမဟုတ် ကိုယ်တိုင်ရိုက်ပြီး လောင်းမလား?: `/b <ပမာဏ>`, `/s <ပမာဏ>`, `/l <ပမာဏ>`\n"
        "    (ဥပမာ: `big 500`, `small100`, `lucky 250` စသည်ဖြင့်ပေါ့!)\n"
        "  _ပွဲတစ်ပွဲတည်းမှာ မတူညီတဲ့ ရလဒ်တွေပေါ် အကြိမ်ပေါင်းများစွာ လောင်းကြေးထပ်လို့ရတယ်နော်။_ \n\n"
        "📊 *သုံးလို့ရတဲ့ အမိန့်တွေ:*\n"
        "  - /score: ကိုယ့်မှာ လက်ရှိ ဘယ်နှစ်မှတ်ရှိလဲ ကြည့်ရအောင်!\n"
        "  - /stats: ကိုယ့်ရဲ့ ဂိမ်းမှတ်တမ်း အသေးစိတ်လေးတွေ ကြည့်ဖို့ပေါ့။\n"
        "  - /leaderboard: ဒီ Chat ထဲက အမှတ်အများဆုံး ထိပ်တန်း ကစားသမားတွေ ဘယ်သူတွေလဲ ကြည့်ရအောင်!\n"
        "  - /history: မကြာသေးခင်က ပွဲစဉ်ရလဒ်လေးတွေ ပြန်ကြည့်ဖို့ပါ။\n\n"
        "👑 *Admin တွေအတွက်ပဲနော်:*\n"
        "  - /startdice: အန်စာတုံးလောင်းကြေးပွဲ အသစ်လေး စတင်လိုက်ရအောင်!\n"
        "  - /adjustscore <user\\_id> <amount>: ကစားသမားတစ်ယောက်ရဲ့ မှတ်တွေကို ထည့်တာ/နှုတ်တာ လုပ်လို့ရတယ်။\n"
        "  - /checkscore <user\\_id or @username>: ကစားသမားတစ်ယောက်ရဲ့ မှတ်တွေနဲ့ အချက်အလက်တွေ စစ်ဆေးကြည့်ဖို့ပေါ့။\n\n"
        "ကဲ... ကံတရားက သင့်ဘက်မှာ အမြဲရှိပါစေရှင့်! 😉", # Feminine, casual tone
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

    chat_specific_data = get_chat_data_for_id(chat_id)
    match_id = chat_specific_data["match_counter"] # Get chat-specific match counter
    chat_specific_data["match_counter"] += 1 # Increment chat-specific match counter
    
    game = DiceGame(match_id, chat_id)
    context.chat_data["game"] = game # Store the game instance in chat-specific data

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("BIG 🔼 (Total > 7)", callback_data="bet_big"),
            InlineKeyboardButton("SMALL 🔽 (Total < 7)", callback_data="bet_small"),
            InlineKeyboardButton("LUCKY 🍀 (Total = 7)", callback_data="bet_lucky")
        ]
    ])

    await context.bot.send_message(
        chat_id,
        f"🔥 *ပွဲစဉ် #{match_id}: လောင်းကြေးတွေ ဖွင့်လိုက်ပါပြီရှင်!* 🔥 \n\n" # Feminine, exciting intro
        "💰 BIG (>7), SMALL (<7), ဒါမှမဟုတ် LUCKY (အတိအကျ 7) တို့ပေါ် လောင်းကြေးထပ်လိုက်ပါနော်။\n" # Feminine instructions
        "ခလုတ်တွေ နှိပ်ပြီး လောင်းမလား (မူရင်း ၁၀၀ မှတ်)! ဒါမှမဟုတ် `big 250`, `s 50`, `lucky100` စသည်ဖြင့် ရိုက်ပြီး လောင်းမလား!?\n"
        "_ပွဲတစ်ပွဲတည်းမှာ မတူညီတဲ့ ရလဒ်တွေပေါ် အကြိမ်ပေါင်းများစွာ လောင်းကြေးထပ်လို့ရတယ်နော်။_ \n\n"
        "⏳ လောင်းကြေးတွေကို *စက္ကန့် ၆၀* အတွင်း ပိတ်တော့မယ်နော်! မြန်မြန်လေး... ကံကြမ္မာက သင့်ကိုစောင့်နေတယ်။ ကံကောင်းပါစေရှင့်! ✨", # Feminine, casual, urgent
        parse_mode="Markdown", reply_markup=keyboard
    )
    logger.info(f"_start_interactive_game_round: Match {match_id} started successfully in chat {chat_id}. Betting open for 60 seconds.")

    # Store the job object in chat_data to allow cancellation
    context.chat_data["close_bets_job"] = context.job_queue.run_once(
        close_bets_scheduled,
        60, # seconds from now
        chat_id=chat_id,
        data=game,
        name=f"close_bets_{chat_id}_{game.match_id}" # Give the job a name for easier identification/debugging
    )
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
    
    num_matches_total = context.chat_data.get("num_matches_total")
    current_match_index = context.chat_data.get("current_match_index")

    if num_matches_total is None or current_match_index is None:
        logger.error(f"_manage_game_sequence: Missing sequence state in chat {chat_id}. Aborting sequence.")
        if "num_matches_total" in context.chat_data: del context.chat_data["num_matches_total"]
        if "current_match_index" in context.chat_data: del context.chat_data["current_match_index"]
        if "game" in context.chat_data: del context.chat_data["game"]
        # Clear next_game_job if sequence state is invalid, as no next game will be scheduled
        if "next_game_job" in context.chat_data:
            del context.chat_data["next_game_job"]
        return

    if current_match_index < num_matches_total:
        logger.info(f"_manage_game_sequence: Starting next game in sequence. Match {current_match_index + 1} of {num_matches_total} for chat {chat_id}.")
        context.chat_data["current_match_index"] += 1
        await _start_interactive_game_round(chat_id, context)
    else:
        logger.info(f"_manage_game_sequence: All {num_matches_total} matches in sequence completed for chat {chat_id}. Cleaning up.")
        if "num_matches_total" in context.chat_data:
            del context.chat_data["num_matches_total"]
        if "current_match_index" in context.chat_data:
            del context.chat_data["current_match_index"]
        if "game" in context.chat_data:
            del context.chat_data["game"]
        # Clear next_game_job here as sequence has finished
        if "next_game_job" in context.chat_data:
            del context.chat_data["next_game_job"]
        await context.bot.send_message(
            chat_id,
            "🎉 *စီစဉ်ထားတဲ့ ပွဲတွေ အားလုံး ပြီးဆုံးသွားပြီနော်!* 🎉\n" # Casual completion
            "နောက်ဆုံး ရမှတ်တွေ ကြည့်ချင်ရင် /leaderboard ကို နှိပ်ပြီး ကြည့်လိုက်ပါဦးနော်။",
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
        await update.message.reply_text(f"Sorry, this bot is not authorized to run in this group ({chat_id}). Please add it to an allowed group.", parse_mode="Markdown")
        return
    # --- END Group ID check ---

    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    logger.info(f"start_dice: User {user_id} ({username}) attempting to start a game in chat {chat_id}")

    chat_specific_data = get_chat_data_for_id(chat_id)
    # Check if admin list for this specific chat is loaded or empty
    if not chat_specific_data["group_admins"]:
        logger.info(f"start_dice: Admin list for chat {chat_id} is empty or not loaded. Attempting to update it now.")
        if not await update_group_admins(chat_id, context):
            await update.message.reply_text(
                "❌ Admin စာရင်းကို ရယူလို့မရသေးဘူးရှင့်။ Bot ကို 'Chat Admins တွေကို ရယူဖို့' ခွင့်ပြုချက် ပေးထားတာ သေချာလား စစ်ပေးပါဦးနော်။ ထပ်ပြီး ကြိုးစားကြည့်ပါဦး။", # Feminine, casual error
                parse_mode="Markdown"
            )
            return

    if not is_admin(chat_id, user_id):
        logger.warning(f"start_dice: User {user_id} is not an admin and tried to start a game in chat {chat_id}.")
        return await update.message.reply_text("❌ Admin တွေပဲ အန်စာတုံးဂိမ်းအသစ်ကို စတင်နိုင်တာပါနော်။", parse_mode="Markdown") # Feminine, casual warning

    current_game = context.chat_data.get("game")
    if current_game and current_game.state != GAME_OVER:
        logger.warning(f"start_dice: Game already active in chat {chat_id}. State: {current_game.state}")
        return await update.message.reply_text("⚠️ ဟိတ်! ဂိမ်းက စနေပြီရှင့်။ အရင်ပွဲလေး ပြီးသွားမှပဲ အသစ်စလို့ရမယ်နော်။ နည်းနည်းလေး စောင့်ပေးပါဦး။", parse_mode="Markdown") # Feminine, casual waiting
    
    if context.chat_data.get("num_matches_total") is not None:
         return await update.message.reply_text("⚠️ ပွဲစဉ်တွေ ဆက်တိုက် စထားပြီးပြီနော်။ လက်ရှိပွဲစဉ်တွေ ပြီးဆုံးသွားတဲ့အထိ စောင့်ပေးပါဦးနော်။", parse_mode="Markdown") # Feminine, casual waiting


    num_matches_requested = 1

    if context.args:
        try:
            num_matches_requested = int(context.args[0])
            if num_matches_requested <= 0:
                return await update.message.reply_text("❌ ပွဲအရေအတွက်က ဂဏန်းအပြုသဘော (positive integer) ဖြစ်ရမယ်နော်။", parse_mode="Markdown") # Feminine, casual error
            elif num_matches_requested > 100: 
                return await update.message.reply_text("❌ တစ်ခါတည်း အန်စာတုံးပွဲ ၁၀၀ ပွဲအထိပဲ စီစဉ်လို့ရပါသေးတယ်နော်။", parse_mode="Markdown") # Feminine, casual limit
        except ValueError:
            await update.message.reply_text(
                "ℹ️ `/startdice` အတွက် မှားယွင်းတဲ့ စာရိုက်ပုံလေး ဖြစ်နေတယ်ရှင့်။ တစ်ပွဲတည်းသော အန်စာတုံးပွဲကိုတော့ စတင်ပေးလိုက်ပါမယ်။\n" # Feminine, casual info
                "အသုံးပြုပုံလေးကတော့: `/startdice` ဆိုရင် တစ်ပွဲစမယ်။ ဒါမှမဟုတ် `/startdice <အရေအတွက်>` ဆိုရင်တော့ ဆက်တိုက်ပွဲများစွာအတွက် သုံးလို့ရပါတယ်။",
                parse_mode="Markdown"
            )
            num_matches_requested = 1


    if num_matches_requested > 1:
        context.chat_data["num_matches_total"] = num_matches_requested
        context.chat_data["current_match_index"] = 0

        await update.message.reply_text(
            f"🎮 ဆက်တိုက် *{num_matches_requested}* ပွဲ စီစဉ်ပေးထားပြီနော်! ပထမပွဲအတွက် အဆင်သင့်ပြင်ထားလိုက်တော့! သွားပြီရှင့်!", # Feminine, casual countdown
            parse_mode="Markdown"
        )
        # Store the job object for sequence management
        context.chat_data["next_game_job"] = context.job_queue.run_once(
            _manage_game_sequence,
            2, # Small delay before first game starts
            chat_id=chat_id,
            name=f"sequence_start_{chat_id}"
        )
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
    
    current_game_in_context = context.chat_data.get("game")
    # Also clear the close_bets_job after it has run
    if "close_bets_job" in context.chat_data:
        del context.chat_data["close_bets_job"]

    if current_game_in_context is None or current_game_in_context != game:
        logger.warning(f"close_bets_scheduled: Skipping action for match {game.match_id} in chat {chat_id} as game instance changed or no game. Current game: {current_game_in_context.match_id if current_game_in_context else 'None'}.")
        return

    game.state = GAME_CLOSED
    logger.info(f"close_bets_scheduled: Bets closed for match {game.match_id} in chat {chat_id}. State set to GAME_CLOSED.")
    
    bet_summary_lines = [
        f"⏳ *ပွဲစဉ် #{game.match_id}: လောင်းကြေးတွေ ပိတ်လိုက်ပါပြီနော်!* ⏳\n", # Feminine, casual closing
        "*လက်ရှိလောင်းကြေးတွေကတော့:*\n"
    ]
    
    has_bets = False
    for bet_type_key, bets_dict in game.bets.items():
        if bets_dict:
            has_bets = True
            bet_summary_lines.append(f"  *{bet_type_key.upper()}* {RESULT_EMOJIS[bet_type_key]}:")
            sorted_bets = sorted(bets_dict.items(), key=lambda item: item[1], reverse=True)
            for uid, amount in sorted_bets:
                player_info = get_chat_data_for_id(chat_id)["player_stats"].get(uid) # Use chat-specific player_stats
                username_display = player_info['username'].replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`') if player_info else f"User {uid}"
                bet_summary_lines.append(f"    → @{username_display}: *{amount}* မှတ်")
    
    if not has_bets:
        bet_summary_lines.append("  ဒီပွဲမှာ ဘယ်သူမှ လောင်းကြေးထပ်မထားကြပါဘူးရှင့်။ စိတ်မကောင်းစရာပဲနော်။") # Feminine, casual empty bets

    bet_summary_lines.append("\nအန်စာတုံးလေးတွေ လှိမ့်နေပြီနော်... အဆင်သင့်ပြင်ထား! 💥") # Exciting
    
    try:
        logger.info(f"close_bets_scheduled: Attempting to send 'Bets closed and summary' message for match {game.match_id} to chat {chat_id}.")
        await context.bot.send_message(chat_id, "\n".join(bet_summary_lines), parse_mode="Markdown")
        logger.info(f"close_bets_scheduled: 'Bets closed and summary' message sent successfully for match {game.match_id}.")
    except Exception as e:
        logger.error(f"close_bets_scheduled: Error sending 'Bets closed' message for chat {chat_id}: {e}", exc_info=True)

    # Store the job object for roll and announce
    context.chat_data["roll_and_announce_job"] = context.job_queue.run_once(
        roll_and_announce_scheduled,
        30, # seconds from now
        chat_id=chat_id,
        data=game,
        name=f"roll_announce_{chat_id}_{game.match_id}"
    )
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
    
    current_game_in_context = context.chat_data.get("game")
    # Also clear the roll_and_announce_job after it has run
    if "roll_and_announce_job" in context.chat_data:
        del context.chat_data["roll_and_announce_job"]

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
    winning_type, multiplier, individual_payouts = game.payout(chat_id)

    result_message_text = (
        f"🎉 *ပွဲစဉ် #{game.match_id} ရဲ့ ရလဒ်တွေ ထွက်ပေါ်လာပါပြီရှင့်!* 🎉\n" # Feminine, exciting results
        f"🎲 *အန်စာတုံးလှိမ့်ကြည့်တော့:* *{d1}* + *{d2}* = *{d1 + d2}* ထွက်လာတယ်!\n" 
        f"🏆 *အနိုင်ရလောင်းကြေးက:* *{winning_type.upper()}* {RESULT_EMOJIS[winning_type]} ပေါ် လောင်းထားသူတွေ *{multiplier} ဆ* ပြန်ရမှာနော်!\n\n" # Feminine, casual payout info
        "*ငွေထုတ်ရရှိသူတွေကတော့:*\n" # Feminine, casual title
    )
    
    chat_specific_data = get_chat_data_for_id(chat_id)
    stats = chat_specific_data["player_stats"] # Use chat-specific player_stats
    
    if individual_payouts:
        payout_lines = []
        sorted_payouts = sorted(
            individual_payouts.items(), 
            key=lambda item: (item[1], stats.get(item[0], {}).get('username', f"User {item[0]}")), 
            reverse=True
        )

        for uid, winnings in sorted_payouts:
            player_info = stats.get(uid)
            if player_info:
                username_display = player_info['username'].replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
                payout_lines.append(f"  ✨ @{username_display}: *+{winnings}* မှတ် ရရှိပြီး အခုရမှတ်: *{player_info['score']}*!") # Feminine, enthusiastic
            else:
                payout_lines.append(f"  ✨ User ID {uid}: *+{winnings}* မှတ် ရရှိခဲ့ပါတယ် (အချက်အလက် မတွေ့ပါ)!") # Feminine, empathetic
        result_message_text += "\n".join(payout_lines)
    else:
        result_message_text += "  ဒီတစ်ပွဲမှာတော့ ဘယ်သူမှ ကံမကောင်းခဲ့ဘူးရှင့်! စိတ်မပျက်ပါနဲ့၊ နောက်ပွဲမှာ အမှတ်တွေ ပုံအောလိုက်နော်! 💔" # Feminine, witty, empathetic loss

    lost_players = []
    for uid in game.participants:
        if uid not in individual_payouts:
            player_info = stats.get(uid)
            if player_info:
                username_display = player_info['username'].replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
                lost_players.append(f"  💀 @{username_display} (ရမှတ်: *{player_info['score']}*) - ကံမကောင်းခဲ့ဘူးရှင့်!") # Feminine, witty
            else:
                lost_players.append(f"  💀 User ID {uid} (ရမှတ်မတွေ့ပါ) - ဘယ်သူဘယ်ဝါမှန်းမသိဘဲ ရှုံးသွားတာလားရှင့်!") # Feminine, witty

    if lost_players:
        result_message_text += "\n\n*ဒီပွဲမှာ ကံစမ်းခဲ့ကြသူတွေ (နဲ့ ကံနည်းသွားသူတွေ):*\n" # Feminine, casual title
        result_message_text += "\n".join(lost_players)


    try:
        logger.info(f"roll_and_announce_scheduled: Attempting to send 'Results' message for match {game.match_id} to chat {chat_id}.")
        await context.bot.send_message(chat_id, result_message_text, parse_mode="Markdown")
        logger.info(f"roll_and_announce_scheduled: 'Results' message sent successfully for match {game.match_id}.")
    except Exception as e:
        logger.error(f"roll_and_announce_scheduled: Error sending 'Results' message for chat {chat_id}: {e}", exc_info=True)

    # --- UPDATED: Idle match logic ---
    chat_specific_data = get_chat_data_for_id(chat_id)
    
    if not game.participants: # No bets were placed in this match
        chat_specific_data["consecutive_idle_matches"] += 1
        logger.info(f"No participants in match {game.match_id}. Consecutive idle matches for chat {chat_id}: {chat_specific_data['consecutive_idle_matches']}")
    else:
        chat_specific_data["consecutive_idle_matches"] = 0 # Reset if bets were placed
        logger.info(f"Participants found in match {game.match_id}. Resetting idle counter for chat {chat_id}.")

    if chat_specific_data["consecutive_idle_matches"] >= 3:
        logger.info(f"Stopping game sequence in chat {chat_id} due to 3 consecutive idle matches.")
        await context.bot.send_message(
            chat_id,
            "😴 *ဂိမ်းရပ်သွားပြီနော်!* 😴\n\n" # Feminine, casual stop
            "ဆက်တိုက် ၃ ပွဲဆက် ဘယ်သူမှ လောင်းကြေးထပ်တာ မတွေ့ရလို့ ဂိမ်းကို ခဏရပ်လိုက်ပါပြီရှင့်။ အမှတ်တွေ ပြန်လည်မလည်တော့ဘူးနော်။"
            "ပြန်ကစားချင်ရင် Admin က /startdice နဲ့ ပြန်စပေးနိုင်ပါတယ်ရှင့်။",
            parse_mode="Markdown"
        )
        # Force stop the game: clear game state and pending jobs
        context.chat_data.pop("game", None)
        context.chat_data.pop("num_matches_total", None)
        context.chat_data.pop("current_match_index", None)
        
        # Cancel any pending sequence/next game jobs
        if "next_game_job" in context.chat_data:
            try:
                context.chat_data["next_game_job"].schedule_removal()
            except JobLookupError:
                logger.warning(f"roll_and_announce_scheduled: JobLookupError for 'next_game_job' during auto-stop for chat {chat_id}.")
            finally:
                del context.chat_data["next_game_job"]
        
        # Ensure other scheduled jobs related to this specific match are also cleared
        if "close_bets_job" in context.chat_data:
            try:
                context.chat_data["close_bets_job"].schedule_removal()
            except JobLookupError:
                logger.warning(f"roll_and_announce_scheduled: JobLookupError for 'close_bets_job' during auto-stop for chat {chat_id}.")
            finally:
                del context.chat_data["close_bets_job"]
        
        # roll_and_announce_job is already popped at the start of this function.
        
        return # Stop further processing for this match, no next game is scheduled
    # --- END UPDATED ---

    if context.chat_data.get("num_matches_total") is not None:
        logger.info(f"roll_and_announce_scheduled: Multi-match sequence active. Scheduling next game in sequence for chat {chat_id}.")
        # Store the job object for the next game in sequence
        context.chat_data["next_game_job"] = context.job_queue.run_once(
            _manage_game_sequence,
            5, # 5-second delay before starting the next game
            chat_id=chat_id,
            name=f"next_game_sequence_{chat_id}"
        )
    else:
        if "game" in context.chat_data:
            del context.chat_data["game"]
            logger.info(f"roll_and_announce_scheduled: Cleaned up game data for chat {chat_id} after single interactive match {game.match_id}.")
        # Also clear next_game_job if it was part of a sequence that just ended
        if "next_game_job" in context.chat_data:
            del context.chat_data["next_game_job"]

    logger.info(f"roll_and_announce_scheduled: Function finished for match {game.match_id} in chat {chat_id}.")


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles inline keyboard button presses for placing bets.
    """
    chat_id = update.effective_chat.id
    # --- Group ID check ---
    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"button_callback: Ignoring callback from disallowed chat ID: {chat_id}")
        await update.callback_query.answer(f"Sorry, this bot is not authorized to run in this group ({chat_id}).", show_alert=True)
        return
    # --- END Group ID check ---

    query = update.callback_query
    await query.answer() 
    
    data = query.data
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name
    
    # Escape username for Markdown
    username_escaped = username.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')

    game = context.chat_data.get("game")
    
    if not game:
        logger.info(f"button_callback: User {user_id} ({username}) tried to bet via button but no game active in chat {chat_id}.")
        return await query.message.reply_text(
            f"⚠️ @{username_escaped} ရေ၊ အန်စာတုံးဂိမ်းက ဘယ်တုန်းကမှ မစသေးဘူးရှင့်။ Admin တစ်ယောက်က /startdice နဲ့ စပေးမှ ရမှာနော်။", # Feminine, casual no game
            parse_mode="Markdown"
        )
    
    if game.state != WAITING_FOR_BETS:
        logger.info(f"button_callback: User {user_id} ({username}) tried to bet via button but betting is closed for match {game.match_id} in chat {chat_id}. State: {game.state}")
        return await query.message.reply_text(
            f"⚠️ @{username_escaped} ရေ၊ ဒီဂိမ်းအတွက် လောင်းကြေးတွေ ပိတ်လိုက်ပြီနော်။ နောက်ပွဲကျမှ ပြန်လာခဲ့ပါဦး!", # Feminine, casual closed bets
            parse_mode="Markdown"
        )

    bet_type = data.split("_")[1]
    
    success, response_message = game.place_bet(user_id, username, bet_type, 100)
    
    # --- UPDATED: Reset idle counter on successful bet ---
    if success:
        chat_specific_data = get_chat_data_for_id(chat_id)
        chat_specific_data["consecutive_idle_matches"] = 0 
        logger.info(f"button_callback: Bet placed by {user_id}, resetting idle counter for chat {chat_id}.")
    # --- END UPDATED ---

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

    game = context.chat_data.get("game")
    if not game:
        logger.info(f"handle_bet: User {user_id} tried to place text bet but no game active in chat {chat_id}.")
        return await update.message.reply_text(
            f"⚠️ @{username_escaped} ရေ၊ အန်စာတုံးဂိမ်းက ဘယ်တုန်းကမှ မစသေးဘူးရှင့်။ Admin တစ်ယောက်က /startdice နဲ့ စပေးမှ ရမှာနော်။", # Feminine, casual no game
            parse_mode="Markdown"
        )
    
    if game.state != WAITING_FOR_BETS:
        logger.info(f"handle_bet: User {user_id} ({username}) tried to place text bet but betting is closed for match {game.match_id} in chat {chat_id}. State: {game.state}")
        return await update.message.reply_text(
            f"⚠️ @{username_escaped} ရေ၊ ဒီဂိမ်းအတွက် လောင်းကြေးတွေ ပိတ်လိုက်ပြီနော်။ နောက်ပွဲကျမှ ပြန်လာခဲ့ပါဦး!", # Feminine, casual closed bets
            parse_mode="Markdown"
        )

    # Simplified regex for single bet parsing
    bet_match = re.match(r"^(big|b|small|s|lucky|l)\s*(\d+)$", message_text, re.IGNORECASE)

    if not bet_match:
        logger.warning(f"handle_bet: Invalid bet format for user {user_id} in message: '{message_text}' in chat {chat_id}.")
        return await update.message.reply_text(
            f"❌ @{username_escaped} ရေ၊ လောင်းကြေးထပ်တာ ပုံစံလေး မှားနေတယ်ရှင့်။ ကျေးဇူးပြုပြီး: `big 500`, `small 100`, `lucky 250` စသည်ဖြင့် ရိုက်ပေးနော်။\n" # Feminine, casual invalid format
            "ခလုတ်တွေ နှိပ်ပြီးတော့လည်း (မူရင်း ၁၀၀ မှတ်) လောင်းလို့ရတယ်နော်!",
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
        return await update.message.reply_text(f"❌ @{username_escaped} ရေ၊ လောင်းကြေးပမာဏက ဂဏန်းဖြစ်ရမှာနော်။", parse_mode="Markdown") # Feminine, casual error

    success, msg = game.place_bet(user_id, username, bet_type, amount)
    
    # --- UPDATED: Reset idle counter on successful bet ---
    if success:
        chat_specific_data = get_chat_data_for_id(chat_id)
        chat_specific_data["consecutive_idle_matches"] = 0
        logger.info(f"handle_bet: Bet placed by {user_id}, resetting idle counter for chat {chat_id}.")
    # --- END UPDATED ---

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
        await update.message.reply_text(f"Sorry, this bot is not authorized to run in this group ({chat_id}). Please add it to an allowed group.", parse_mode="Markdown")
        return
    # --- END Group ID check ---

    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    logger.info(f"show_score: User {user_id} ({username}) requested score in chat {chat_id}")

    chat_specific_data = get_chat_data_for_id(chat_id)
    player_stats = chat_specific_data["player_stats"].get(user_id) # Use chat-specific player_stats

    if player_stats:
        await update.message.reply_text(
            f"📊 အော်.. သင့်ရမှတ်ကတော့ *{player_stats['score']}* မှတ်တောင် ရှိနေပြီနော်!\n" # Feminine, casual score
            f"✅ အနိုင်ရခဲ့တာ: *{player_stats['wins']}* ပွဲ | ❌ ရှုံးနိမ့်ခဲ့တာ: *{player_stats['losses']}* ပွဲ", # Feminine, casual win/loss
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "ℹ️ ဒီ Chat ထဲမှာ ဂိမ်းတွေ မကစားရသေးဘူးရှင့်။ Admin တစ်ယောက်ကို /startdice နဲ့ ဂိမ်းစဖို့ ပြောပြီး အမှတ်တွေ စယူလိုက်ပါဦးနော်!", # Feminine, casual no game
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
        await update.message.reply_text(f"Sorry, this bot is not authorized to run in this group ({chat_id}). Please add it to an allowed group.", parse_mode="Markdown")
        return
    # --- END Group ID check ---

    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    logger.info(f"show_stats: User {user_id} ({username}) requested detailed stats in chat {chat_id}")

    chat_specific_data = get_chat_data_for_id(chat_id)
    player_stats = chat_specific_data["player_stats"].get(user_id) # Use chat-specific player_stats

    if player_stats:
        total_games = player_stats['wins'] + player_stats['losses']
        win_rate = 0.0 
        if total_games > 0:
            win_rate = (player_stats['wins'] / total_games) * 100


        username_display = player_stats['username'].replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')

        await update.message.reply_text(
            f"👤 *@{username_display}* ရဲ့ အချက်အလက်လေးတွေကတော့:\n" # Feminine, casual intro
            f"  အမှတ်: *{player_stats['score']}* မှတ်\n" 
            f"  ကစားခဲ့တဲ့ပွဲ: *{total_games}* ပွဲ\n" 
            f"  ✅ အနိုင်ရခဲ့တာ: *{player_stats['wins']}* ပွဲ\n" 
            f"  ❌ ရှုံးနိမ့်ခဲ့တာ: *{player_stats['losses']}* ပွဲ\n" 
            f"  အနိုင်ရနှုန်း: *{win_rate:.1f}%* (ကြမ်းသလောက် မဆိုးပါဘူးနော်!)\n" # Feminine, witty comment
            f"  နောက်ဆုံးလှုပ်ရှားခဲ့တဲ့အချိန်: *{player_stats['last_active'].strftime('%Y-%m-%d %H:%M')}*", # Feminine, casual time
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("ℹ️ ဟိတ်! သင့်အတွက် အချက်အလက်တွေ မတွေ့ရသေးဘူးနော်။ ဂိမ်းစပြီး ကစားလိုက်ပါဦး၊ ပြီးမှ မှတ်တမ်းတင်ပေးမယ်ရှင့်!", parse_mode="Markdown") # Feminine, casual no stats

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Displays the top 10 players by score in the current chat.
    Filters out players who haven't made any bets (still on initial 1000 points).
    """
    chat_id = update.effective_chat.id
    # --- Group ID check ---
    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"leaderboard: Ignoring command from disallowed chat ID: {chat_id}")
        await update.message.reply_text(f"Sorry, this bot is not authorized to run in this group ({chat_id}). Please add it to an allowed group.", parse_mode="Markdown")
        return
    # --- END Group ID check ---

    logger.info(f"leaderboard: User {update.effective_user.id} requested leaderboard in chat {chat_id}")

    chat_specific_data = get_chat_data_for_id(chat_id)
    stats_for_chat = chat_specific_data["player_stats"] # Use chat-specific player_stats
    
    active_players = [
        p for p in stats_for_chat.values()
        if p["wins"] > 0 or p["losses"] > 0 or p["score"] != INITIAL_PLAYER_SCORE
    ]
    top_players = sorted(active_players, key=lambda x: x["score"], reverse=True)[:10]

    if not top_players:
        return await update.message.reply_text("ℹ️ ဒီ Chat ထဲမှာတော့ မှတ်တမ်းတင်ထားတဲ့ ကစားသမားတွေ မရှိသေးဘူးရှင့်။ ဂိမ်းစပြီး လောင်းကြေးထပ်လိုက်မှပဲ အမှတ်တွေတက်လာမှာနော်။", parse_mode="Markdown") # Feminine, casual no players
    
    message_lines = ["🏆 *ဒီ Chat ထဲက ထိပ်တန်းကစားသမားတွေ (ဦးဆောင်ဘုတ်) ကတော့:*\n"] # Feminine, casual title
    for i, player in enumerate(top_players):
        username_display = player['username'].replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
        message_lines.append(f"{i+1}. @{username_display}: *{player['score']}* မှတ် (အမိုက်စားပဲနော်!)") # Feminine, witty comment
    
    await update.message.reply_text("\n".join(message_lines), parse_mode="Markdown")


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Displays the recent match history for the current chat (last 5 matches).
    """
    chat_id = update.effective_chat.id
    # --- Group ID check ---
    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"history: Ignoring command from disallowed chat ID: {chat_id}")
        await update.message.reply_text(f"Sorry, this bot is not authorized to run in this group ({chat_id}). Please add it to an allowed group.", parse_mode="Markdown")
        return
    # --- END Group ID check ---

    logger.info(f"history: User {update.effective_user.id} requested match history in chat {chat_id}")

    chat_specific_data = get_chat_data_for_id(chat_id)
    match_history_for_chat = chat_specific_data["match_history"] # Use chat-specific match_history
    
    if not match_history_for_chat:
        return await update.message.reply_text("ℹ️ ဒီ Chat ထဲမှာတော့ ပွဲမှတ်တမ်းတွေ မရှိသေးဘူးရှင့်။ မှတ်တမ်းတွေ ဖန်တီးချင်ရင် ဂိမ်းတွေ များများ ကစားပါဦးနော်။", parse_mode="Markdown") # Feminine, casual no history
    
    message_lines = ["📜 *မကြာသေးခင်က ပြီးသွားတဲ့ပွဲတွေ (နောက်ဆုံး ၅ ပွဲ) ကတော့:*\n"] # Feminine, casual title
    for match in match_history_for_chat[-5:][::-1]: 
        timestamp_str = match['timestamp'].strftime('%Y-%m-%d %H:%M')
        winner_display = match['winner'].upper().replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
        winner_emoji = RESULT_EMOJIS.get(match['winner'], '')
        
        message_lines.append(
            f"  • ပွဲစဉ် #{match['match_id']} | ရလဒ်: *{match['result']}* ({winner_display} {winner_emoji}) | ပါဝင်ကစားသူ: *{match['participants']}* ယောက် | အချိန်: {timestamp_str}" # Feminine, casual details
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
        await update.message.reply_text(f"Sorry, this bot is not authorized to run in this group ({chat_id}). Please add it to an allowed group.", parse_mode="Markdown")
        return
    # --- END Group ID check ---

    requester_user_id = update.effective_user.id
    logger.info(f"adjust_score: User {requester_user_id} attempting to adjust score in chat {chat_id}")

    if not is_admin(chat_id, requester_user_id):
        logger.warning(f"adjust_score: User {requester_user_id} is not an admin and tried to adjust score in chat {chat_id}.")
        return await update.message.reply_text("❌ Admin တွေပဲ ကစားသမားမှတ်တွေကို ချိန်ညှိခွင့်ရှိတာနော်။", parse_mode="Markdown") # Feminine, casual admin check

    target_user_id = None
    amount_to_adjust = None
    target_username_display = None

    if update.message.reply_to_message:
        if not context.args or len(context.args) != 1:
            return await update.message.reply_text(
                "❌ ပြန်ဖြေပြီး သုံးတာ ပုံစံလေး မှားနေတယ်ရှင့်။ ကျေးဇူးပြုပြီး: `/adjustscore <ပမာဏ>` ကိုပဲ သုံးပေးပါနော်။\n" # Feminine, casual invalid usage
                "ဥပမာ- အသုံးပြုသူရဲ့ မက်ဆေ့ချ်ကို ပြန်ဖြေပြီး `/adjustscore 500` (၅၀၀ မှတ် ထည့်ဖို့ပေါ့) လို့ ရိုက်လိုက်ပါ။",
                parse_mode="Markdown"
            )
        
        target_user_id = update.message.reply_to_message.from_user.id
        target_username_display = update.message.reply_to_message.from_user.username or update.message.reply_to_message.from_user.first_name
        
        try:
            amount_to_adjust = int(context.args[0])
        except ValueError:
            return await update.message.reply_text(
                "❌ ပမာဏက ဂဏန်းဖြစ်ရမှာနော်။ မှားနေတယ်ရှင့်။\n" # Feminine, casual error
                "ဥပမာ- အသုံးပြုသူရဲ့ မက်ဆေ့ချ်ကို ပြန်ဖြေပြီး `/adjustscore 500` လို့ ရိုက်လိုက်ပါ။",
                parse_mode="Markdown"
            )

    elif context.args and len(context.args) >= 2:
        first_arg = context.args[0]
        try:
            amount_to_adjust = int(context.args[1])
        except ValueError:
            return await update.message.reply_text(
                "❌ ပမာဏက ဂဏန်းဖြစ်ရမှာနော်။ မှားနေတယ်ရှင့်။\n" # Feminine, casual error
                "ဥပမာ- `/adjustscore 123456789 500` ဒါမှမဟုတ် `/adjustscore @someuser 100` စသည်ဖြင့် သုံးပါနော်။",
                parse_mode="Markdown"
            )

        chat_specific_data = get_chat_data_for_id(chat_id)
        
        if first_arg.startswith('@'):
            mentioned_username = first_arg[1:]
            
            # Try to find user in bot's in-memory player_stats first
            for uid, player_info in chat_specific_data["player_stats"].items():
                if player_info.get("username", "").lower() == mentioned_username.lower():
                    target_user_id = uid
                    target_username_display = player_info.get("username")
                    break
            
            if target_user_id is None: # User not found in local player_stats by username
                try:
                    return await update.message.reply_text(
                        f"❌ အသုံးပြုသူ '@{mentioned_username}' ကို ဒီ Chat ရဲ့ ဂိမ်းအချက်အလက်တွေထဲမှာ ရှာမတွေ့ဘူးရှင့်။ သူတို့က Bot နဲ့ ဒီ Chat မှာ အရင်က ဆော့ဖူးမှ ရမှာနော်။ ဒါမှမဟုတ် သူတို့ပို့ထားတဲ့ မက်ဆေ့ချ်ကို ပြန်ဖြေပြီး သုံးတာ ဒါမှမဟုတ် သူတို့ရဲ့ User ID ကို ဂဏန်းနဲ့ ရိုက်ပြီး သုံးကြည့်ပါလား။", # Feminine, casual explanation
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.warning(f"adjust_score: Attempt to fetch user {mentioned_username} by username via get_chat_member failed: {e}")
                    pass # Continue to the check below for None target_user_id
        else: # Numeric user ID provided
            try:
                target_user_id = int(first_arg)
            except ValueError:
                return await update.message.reply_text(
                    "❌ User ID ဒါမှမဟုတ် ပမာဏက မှားနေတယ်ရှင့်။ ကျေးဇူးပြုပြီး: `/adjustscore <user_id>` ဒါမှမဟုတ် `/adjustscore @username <ပမာဏ>` ကိုသုံးပေးနော်။\n" # Feminine, casual error
                    "ဥပမာ- `/adjustscore 123456789 500` ဒါမှမဟုတ် `/adjustscore @someuser 100`။",
                    parse_mode="Markdown"
                )
            
    else: # Neither reply nor valid direct args
        return await update.message.reply_text(
            "❌ သုံးတဲ့ပုံစံလေး မှားနေတယ်နော်။ ကျေးဇူးပြုပြီး အောက်က ပုံစံတွေထဲက တစ်ခုခုကို သုံးပေးပါ:\n" # Feminine, casual invalid usage
            "  - အသုံးပြုသူရဲ့ မက်ဆေ့ချ်ကို ပြန်ဖြေပြီး: `/adjustscore <ပမာဏ>`\n"
            "  - တိုက်ရိုက်ရိုက်ထည့်ချင်ရင်: `/adjustscore <user_id>`\n"
            "  - Username နဲ့ ရိုက်ထည့်ချင်ရင်: `/adjustscore @username <ပမာဏ>`\n"
            "ဥပမာ- `/adjustscore 123456789 500` ဒါမှမဟုတ် `/adjustscore @someuser 100`။",
            parse_mode="Markdown"
        )

    if target_user_id is None or amount_to_adjust is None:
        logger.error(f"adjust_score: Logic error: target_user_id ({target_user_id}) or amount_to_adjust ({amount_to_adjust}) is None after initial parsing. update_message: {update.message.text}")
        return await update.message.reply_text("❌ မထင်မှတ်ထားတဲ့ ပြဿနာလေး ဖြစ်သွားတယ်ရှင့်။ ကျေးဇူးပြုပြီး ထပ်ကြိုးစားကြည့်ပါဦးနော် ဒါမှမဟုတ် Admin ကို အကူအညီတောင်းပါ။", parse_mode="Markdown") # Feminine, casual error

    chat_specific_data = get_chat_data_for_id(chat_id)
    player_stats_for_chat = chat_specific_data["player_stats"]
    target_player_stats = player_stats_for_chat.get(target_user_id)

    if not target_player_stats:
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
                f"❌ User ID `{target_user_id}` နဲ့ ကစားသမားကို ဒီ Chat ထဲမှာ ရှာမတွေ့ဘူးရှင့်။ Telegram က သူတို့ရဲ့ အချက်အလက်တွေကို ရယူလို့မရလို့ပါ။ သူတို့က ဒီ Chat ရဲ့ အဖွဲ့ဝင် ဟုတ်မဟုတ် သေချာအောင် စစ်ပေးပါဦးနော် ဒါမှမဟုတ် သူတို့ရဲ့ မက်ဆေ့ချ်တစ်ခုကို ပြန်ဖြေကြည့်ပါ။", # Feminine, casual error with context
                parse_mode="Markdown"
            )
            
    if target_username_display is None:
        target_username_display = target_player_stats.get('username', f"User {target_user_id}")

    old_score = target_player_stats['score']
    target_player_stats['score'] += amount_to_adjust
    target_player_stats['last_active'] = datetime.now() 
    new_score = target_player_stats['score']

    username_display_escaped = target_username_display.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')

    await update.message.reply_text(
        f"✅ @{username_display_escaped} (ID: `{target_user_id}`) ရဲ့ ရမှတ်ကို *{amount_to_adjust}* မှတ် ချိန်ညှိပြီးပါပြီနော်။\n" # Feminine, casual confirmation
        f"အရင်ရမှတ်: *{old_score}* မှတ် | အခုရမှတ်: *{new_score}* မှတ်။ (ကဲ... အမှတ်တွေ ပြောင်းသွားပြီနော်!)", # Feminine, witty update
        parse_mode="Markdown"
    )
    logger.info(f"adjust_score: User {requester_user_id} adjusted score for {target_user_id} in chat {chat_id} by {amount_to_adjust}. New score: {new_score}")

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
        await update.message.reply_text(f"Sorry, this bot is not authorized to run in this group ({chat_id}). Please add it to an allowed group.", parse_mode="Markdown")
        return
    # --- END Group ID check ---

    requester_user_id = update.effective_user.id
    logger.info(f"check_user_score: User {requester_user_id} attempting to check score in chat {chat_id}")

    if not is_admin(chat_id, requester_user_id):
        logger.warning(f"check_user_score: User {requester_user_id} is not an admin and tried to check score in chat {chat_id}.")
        return await update.message.reply_text("❌ Admin တွေပဲ တခြားကစားသမားတွေရဲ့ ရမှတ်တွေကို စစ်ဆေးကြည့်လို့ရတာနော်။", parse_mode="Markdown") # Feminine, casual admin check

    target_user_id = None
    target_username_display = None

    if update.message.reply_to_message:
        target_user_id = update.message.reply_to_message.from_user.id
        target_username_display = update.message.reply_to_message.from_user.username or update.message.reply_to_message.from_user.first_name
        logger.info(f"check_user_score: Admin {requester_user_id} checking score by reply for user {target_user_id}.")
    elif context.args and len(context.args) == 1:
        first_arg = context.args[0]
        
        if first_arg.startswith('@'):
            mentioned_username = first_arg[1:]
            
            chat_specific_data = get_chat_data_for_id(chat_id)
            # Try to find user in bot's in-memory player_stats first
            for uid, player_info in chat_specific_data["player_stats"].items():
                if player_info.get("username", "").lower() == mentioned_username.lower():
                    target_user_id = uid
                    target_username_display = player_info.get("username")
                    break
            
            if target_user_id is None: # User not found in local player_stats by username
                try:
                    return await update.message.reply_text(
                        f"❌ အသုံးပြုသူ '@{mentioned_username}' ကို ဒီ Chat ရဲ့ ဂိမ်းအချက်အလက်တွေထဲမှာ ရှာမတွေ့ဘူးရှင့်။ သူတို့က Bot နဲ့ ဒီ Chat မှာ အရင်က ဆော့ဖူးမှ ရမှာနော်။ ဒါမှမဟုတ် သူတို့ပို့ထားတဲ့ မက်ဆေ့ချ်ကို ပြန်ဖြေပြီး သုံးတာ ဒါမှမဟုတ် သူတို့ရဲ့ User ID ကို ဂဏန်းနဲ့ ရိုက်ပြီး သုံးကြည့်ပါလား။", # Feminine, casual explanation
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.warning(f"check_user_score: Attempt to fetch user {mentioned_username} by username via get_chat_member failed: {e}")
                    pass # Continue to the check below for None target_user_id
        else: # Numeric user ID provided
            try:
                target_user_id = int(first_arg)
                logger.info(f"check_user_score: Admin {requester_user_id} checking score by numeric ID for user {target_user_id}.")
            except ValueError:
                return await update.message.reply_text(
                    "❌ User ID ဒါမှမဟုတ် ပမာဏက မှားနေတယ်ရှင့်။ ကျေးဇူးပြုပြီး: `/checkscore <user_id>` ဒါမှမဟုတ် `/checkscore @username` ကိုသုံးပေးနော်။\n" # Feminine, casual error
                    "ဥပမာ- `/checkscore 123456789` ဒါမှမဟုတ် `/checkscore @someuser`။",
                    parse_mode="Markdown"
                )
    else:
        return await update.message.reply_text(
            "❌ သုံးတဲ့ပုံစံလေး မှားနေတယ်နော်။ ကျေးဇူးပြုပြီး အောက်က ပုံစံတွေထဲက တစ်ခုခုကို သုံးပေးပါ:\n" # Feminine, casual invalid usage
            "  - အသုံးပြုသူရဲ့ မက်ဆေ့ချ်ကို ပြန်ဖြေပြီး: `/checkscore`\n"
            "  - တိုက်ရိုက်ရိုက်ထည့်ချင်ရင်: `/checkscore <user_id>`\n"
            "  - Username နဲ့ ရိုက်ထည့်ချင်ရင်: `/checkscore @username`\n"
            "ဥပမာ- `/checkscore 123456789` ဒါမှမဟုတ် `/checkscore @someuser`။",
            parse_mode="Markdown"
        )

    if target_user_id is None:
        logger.error(f"check_user_score: Logic error: target_user_id ({target_user_id}) is None after initial parsing. update_message: {update.message.text}")
        return await update.message.reply_text("❌ မထင်မှတ်ထားတဲ့ ပြဿနာလေး ဖြစ်သွားတယ်ရှင့်။ ကျေးဇူးပြုပြီး ထပ်ကြိုးစားကြည့်ပါဦးနော် ဒါမှမဟုတ် Admin ကို အကူအညီတောင်းပါ။", parse_mode="Markdown") # Feminine, casual error

    chat_specific_data = get_chat_data_for_id(chat_id)
    player_stats = chat_specific_data["player_stats"].get(target_user_id)

    if not player_stats:
        try:
            chat_member = await context.bot.get_chat_member(chat_id, target_user_id)
            fetched_username = chat_member.user.username or chat_member.user.first_name
            username_display_escaped = fetched_username.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
            
            await update.message.reply_text(
                f"👤 *@{username_display_escaped}* (ID: `{target_user_id}`) မှာတော့ ဒီ Chat အတွက် ဂိမ်းမှတ်တမ်းတွေ မရှိသေးဘူးရှင့်။\n" # Feminine, casual no stats
                f"သူတို့ရဲ့ လက်ရှိရမှတ်ကတော့ *{INITIAL_PLAYER_SCORE}* မှတ်ပဲ ရှိသေးတာပေါ့နော်။", # Feminine, casual score
                parse_mode="Markdown"
            )
            logger.info(f"check_user_score: Admin {requester_user_id} checked score for new user {target_user_id} (no stats yet).")
            return # Exit after informing user

        except Exception as e:
            logger.error(f"check_user_score: Failed to find player {target_user_id} or fetch their details in chat {chat_id}: {e}", exc_info=True)
            return await update.message.reply_text(
                f"❌ User ID `{target_user_id}` နဲ့ ကစားသမားကို ဒီ Chat ထဲမှာ ရှာမတွေ့ဘူးရှင့်။ Telegram က သူတို့ရဲ့ အချက်အလက်တွေကို ရယူလို့မရလို့ပါ။ သူတို့က ဒီ Chat ရဲ့ အဖွဲ့ဝင် ဟုတ်မဟုတ် သေချာအောင် စစ်ပေးပါဦးနော် ဒါမှမဟုတ် သူတို့ရဲ့ မက်ဆေ့ချ်တစ်ခုကို ပြန်ဖြေကြည့်ပါ။", # Feminine, casual error with context
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
        f"👤 *@{username_display_escaped}* ရဲ့ အချက်အလက်တွေ (ID: `{target_user_id}`) ကတော့:\n" # Feminine, casual intro
        f"  အမှတ်: *{player_stats['score']}* မှတ်\n"
        f"  ကစားခဲ့တဲ့ပွဲ: *{total_games}* ပွဲ\n"
        f"  ✅ အနိုင်ရခဲ့တာ: *{player_stats['wins']}* ပွဲ\n"
        f"  ❌ ရှုံးနိမ့်ခဲ့တာ: *{player_stats['losses']}* ပွဲ\n"
        f"  အနိုင်ရနှုန်း: *{win_rate:.1f}%* (ကြမ်းသလောက် မဆိုးပါဘူးနော်!)\n" # Feminine, witty comment
        f"  နောက်ဆုံးလှုပ်ရှားခဲ့တဲ့အချိန်: *{player_stats['last_active'].strftime('%Y-%m-%d %H:%M')}*", # Feminine, casual time
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
        await update.message.reply_text(f"Sorry, this bot is not authorized to run in this group ({chat_id}). Please add it to an allowed group.", parse_mode="Markdown")
        return
    # --- END Group ID check ---

    user_id = update.effective_user.id

    # Allow hardcoded global admins to use this even if group_admins isn't yet populated
    if not is_admin(chat_id, user_id) and user_id not in HARDCODED_ADMINS:
        logger.warning(f"refresh_admins: User {user_id} tried to refresh admins in chat {chat_id} but is not an admin.")
        return await update.message.reply_text("❌ Admin တွေပဲ Admin စာရင်းကို ပြန် Refresh လုပ်လို့ရတာနော်။", parse_mode="Markdown") # Feminine, casual admin check

    logger.info(f"refresh_admins: User {user_id} attempting to refresh admin list for chat {chat_id}.")
    
    if await update_group_admins(chat_id, context):
        await update.message.reply_text("✅ Admin စာရင်းကို အောင်မြင်စွာ ပြန် Refresh လုပ်ပြီးပါပြီရှင့်! အခုဆို အချက်အလက်တွေ အသစ်ဖြစ်သွားပြီနော်။", parse_mode="Markdown") # Feminine, casual success
    else:
        await update.message.reply_text(
            "❌ Admin စာရင်းကို ပြန် Refresh လုပ်လို့ မရသေးဘူးရှင့်။ Bot ကို 'Chat Admins တွေကို ရယူဖို့' ခွင့်ပြုချက် ပေးထားတာ သေချာလား စစ်ပေးပါဦးနော်။", # Feminine, casual error
            parse_mode="Markdown"
        )


async def stop_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Admin command to forcefully stop the current game (if active) and refund all placed bets.
    This can be used to interrupt a game or a sequence of games.
    
    Args:
        update (Update): The update object containing the /stop command.
        context (ContextTypes.DEFAULT_TYPE): The context object.
    """
    chat_id = update.effective_chat.id

    if chat_id not in ALLOWED_GROUP_IDS:
        logger.info(f"stop_game: Ignoring command from disallowed chat ID: {chat_id}")
        await update.message.reply_text(f"Sorry, this bot is not authorized to run in this group ({chat_id}). Please add it to an allowed group.", parse_mode="Markdown")
        return

    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    logger.info(f"stop_game: User {user_id} ({username}) attempting to stop a game in chat {chat_id}")

    if not is_admin(chat_id, user_id): # Check if the requester is an admin
        logger.warning(f"stop_game: User {user_id} is not an admin and tried to stop a game in chat {chat_id}.")
        return await update.message.reply_text("❌ Admin တွေပဲ လက်ရှိဂိမ်းကို ရပ်တန့်လို့ရပါတယ်နော်。", parse_mode="Markdown")

    # Access the game object directly from context.chat_data
    current_game = context.chat_data.get("game")

    if not current_game:
        logger.info(f"stop_game: No game object found in chat_data for chat {chat_id}.")
        return await update.message.reply_text(
            "ℹ️ လက်ရှိစတင်ထားတဲ့ အန်စာတုံးဂိမ်း မရှိသေးဘူးရှင့်။ ရပ်ဖို့လည်း မလိုဘူးပေါ့! စတင်ဖို့ Admin က /startdice နဲ့ စရမယ်နော်။", # Feminine, witty, casual no game
            parse_mode="Markdown"
        )
    
    if current_game.state == GAME_OVER:
        logger.info(f"stop_game: Game is already GAME_OVER for match {current_game.match_id} in chat {chat_id}.")
        return await update.message.reply_text(
            f"ℹ️ ပွဲစဉ် #{current_game.match_id} က ပြီးသွားပါပြီရှင့်။ ပြီးသွားတဲ့ပွဲကို ရပ်လို့မရဘူးနော်။ နောက်ပွဲကျမှ ကြိုးစားကြည့်ပါ!", # Feminine, witty, casual finished game
            parse_mode="Markdown"
        )

    # List of job keys to attempt to cancel and remove from chat_data
    job_keys_to_clear = ["close_bets_job", "roll_and_announce_job", "next_game_job"]
    
    for job_key in job_keys_to_clear:
        job = context.chat_data.get(job_key)
        if job:
            try:
                job.schedule_removal()
                logger.info(f"stop_game: Canceled job '{job.name}' ({job_key}) for chat {chat_id}.")
            except JobLookupError:
                logger.warning(f"stop_game: Job '{job_key}' with ID '{job.id}' for chat {chat_id} was already removed or never existed. Continuing.")
            except Exception as e:
                logger.error(f"stop_game: Unexpected error canceling job '{job_key}' for chat {chat_id}: {e}", exc_info=True)
            finally:
                # Always remove the job reference from chat_data after attempting to remove it
                context.chat_data.pop(job_key, None)
                logger.debug(f"stop_game: Cleared job reference '{job_key}' from chat_data for chat {chat_id}.")


    refunded_players_info = []
    player_stats_for_chat = get_chat_data_for_id(chat_id)["player_stats"]

    # Process refunds for all bets placed in the current game
    total_refunded_amount = 0
    total_bets_by_user = {} # Aggregate total bets per user across all bet types

    for bet_type_dict in current_game.bets.values():
        for uid, amount_bet in bet_type_dict.items():
            total_bets_by_user[uid] = total_bets_by_user.get(uid, 0) + amount_bet
    
    for uid, refunded_amount in total_bets_by_user.items():
        if uid in player_stats_for_chat:
            player_stats = player_stats_for_chat[uid]
            player_stats["score"] += refunded_amount # Add refunded amount back to score
            player_stats["last_active"] = datetime.now() # Update last active time
            total_refunded_amount += refunded_amount
            
            username_display = player_stats['username'].replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
            refunded_players_info.append(
                f"  @{username_display}: *+{refunded_amount}* မှတ် (အခုရမှတ်: *{player_stats['score']}*)"
            )
            logger.info(f"stop_game: Refunded {refunded_amount} to user {uid} in chat {chat_id}. New score: {player_stats['score']}")
        else:
            logger.warning(f"stop_game: Could not find player {uid} in stats for refund in chat {chat_id}.")

    # Clear the current game instance and any sequence-related state from context.chat_data
    context.chat_data.pop("game", None)
    context.chat_data.pop("num_matches_total", None)
    context.chat_data.pop("current_match_index", None)
    # The individual job keys should already be popped by the loop above, but ensure it.
    context.chat_data.pop("close_bets_job", None)
    context.chat_data.pop("roll_and_announce_job", None)
    context.chat_data.pop("next_game_job", None) # Clear the sequence job as well

    refund_message = f"🛑 *ပွဲစဉ် #{current_game.match_id} ကို အတင်းရပ်တန့်လိုက်ပါပြီရှင့်!* 🛑\n\n" # Feminine, more emphatic stop
    if refunded_players_info:
        refund_message += "*လောင်းကြေးတွေ အားလုံး ပြန်အမ်းပေးလိုက်ပြီနော်:*\n"
        refund_message += "\n".join(refunded_players_info)
        refund_message += f"\n\nစုစုပေါင်း ပြန်အမ်းပေးလိုက်တဲ့အမှတ်: *{total_refunded_amount}* မှတ်။ (ကဲ... အမှတ်တွေ ပြန်ရပြီဆိုတော့ ပြုံးလိုက်တော့! 😊)"
    else:
        refund_message += "ဒီပွဲမှာ ဘယ်သူမှ မလောင်းထားတော့ ပြန်အမ်းစရာ မရှိဘူးရှင့်။ (အားနာလိုက်တာနော် 😅)" # Feminine, witty no refunds

    await update.message.reply_text(refund_message, parse_mode="Markdown")
    logger.info(f"stop_game: Match {current_game.match_id} successfully stopped and bets refunded in chat {chat_id}.")
