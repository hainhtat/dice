import logging
import asyncio # For async.sleep
from datetime import datetime
import random # For random.randint fallback in dice roll
import re # Import the 're' module for regex operations

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes # Only ContextTypes is needed here from telegram.ext

# Import necessary components from other modules
from game_logic import DiceGame, WAITING_FOR_BETS, GAME_CLOSED, GAME_OVER, get_chat_data_for_id # Import get_chat_data_for_id
# --- UPDATED: Import ALLOWED_GROUP_IDS from constants.py ---
from constants import global_data, HARDCODED_ADMINS, RESULT_EMOJIS, INITIAL_PLAYER_SCORE, ALLOWED_GROUP_IDS
# --- END UPDATED ---

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
                    "🎉 *အန်စာတုံးဂိမ်းမှ ကြိုဆိုပါတယ်။* 🎉\n"
                    "ကံစမ်းဖို့ အသင့်ပဲလား? အုပ်ချုပ်သူများက /startdice ဖြင့် စတင်ပါ။ ကစားသမားများက မိမိတို့၏ /score ကို ကြည့်ရှုပြီး လောင်းကြေးထပ်ပါ။ ကံကောင်းပါစေ!\n",
                    parse_mode="Markdown"
                )
            else:
                await context.bot.send_message(
                    chat_id,
                    "👋 ဟိုင်း! ကျွန်တော်က အန်စာတုံးဂိမ်းဘော့တ်ပါ။ အုပ်ချုပ်သူစာရင်းကို ရယူရာတွင် အခက်အခဲရှိနေပုံရသည်။ 'ချတ်အုပ်ချုပ်သူများကို ရယူရန်' ခွင့်ပြုချက်ရှိကြောင်း သေချာပါစေ။",
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
        "🌟🎲 *Welcome to the Ultimate Rangoon Dice Showdown!* 🎉�\n\n"
        "ကံကောင်းဖို့ အသင့်ပဲလား? ကစားနည်း:\n\n"
        "✨ *ဂိမ်းစည်းမျဉ်း:* အံစာတုံး ၂ ခုလှည့်ပါမယ်. ရလဒ်ကို ခန့်မှန်းပါ။\n"
        "  - *BIG* 🔼: ၇ ထက်ကြီး (၂ ဆ ပြန်ရ)\n"
        "  - *SMALL* 🔽: ၇ ထက်ငယ်(၂ ဆ ပြန်ရ)\n"
        "  - *LUCKY* 🍀: ၇ (၅ ဆ ပြန်ရ)\n\n"
        "💰 *ဘယ်လိုလောင်းမလဲ:*\n"
        "  - လောင်းကြေးထပ်ချိန် (မူရင်း ၁၀၀ မှတ်) အတွင်း ခလုတ်များကို နှိပ်ပါ။\n"
        "  - သို့မဟုတ် ရိုက်ပါ: `/b <ပမာဏ>`, `/s <ပမာဏ>`, `/l <ပမာဏ>`\n"
        "    (ဥပမာ: `big 500`, `small100`, `lucky 250`)\n"
        "  _ပွဲတစ်ပွဲတည်းမှာ မတူညီတဲ့ ရလဒ်တွေပေါ် အကြိမ်ပေါင်းများစွာ လောင်းကြေးထပ်နိုင်ပါတယ်။_ \n\n"
        "📊 *အမိန့်များ:*\n"
        "  - /score: သင်၏ လက်ရှိမှတ်များကို ကြည့်ပါ။\n"
        "  - /stats: သင်၏ အသေးစိတ်ကိုယ်ပိုင်ဂိမ်းစာရင်းအင်းများကို ကြည့်ပါ။\n"
        "  - /leaderboard: ဤချတ်ရှိ ထိပ်တန်းကစားသမားများကို ကြည့်ပါ။\n"
        "  - /history: မကြာသေးမီက ပွဲစဉ်ရလဒ်များကို ကြည့်ပါ။\n\n"
        "👑 *အုပ်ချုပ်သူများအတွက်သာ:*\n"
        "  - /startdice: အန်စာတုံး လောင်းကြေးပွဲအသစ် စတင်ပါ။\n"
        "  - /adjustscore <user\\_id> <amount>: ကစားသမားတစ်ဦးအတွက် မှတ်များ ထည့်သွင်း/နှုတ်ယူပါ။\n"
        "  - /checkscore <user\\_id or @username>: ကစားသမားတစ်ဦး၏ မှတ်များနှင့် စာရင်းအင်းများကို စစ်ဆေးပါ။\n\n"
        "ကံတရားက သင့်ဘက်မှာ အမြဲရှိပါစေ! 😉",
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
        f"🔥 *ပွဲစဉ် #{match_id}: လောင်းကြေးဖွင့်ပါပြီ!* 🔥\n\n"
        "💰 BIG (>7), SMALL (<7), သို့မဟုတ် LUCKY (အတိအကျ 7) တို့ပေါ် လောင်းကြေးထပ်ပါ။\n"
        "ခလုတ်များ (မူရင်း ၁၀၀ မှတ်) ကိုသုံးပါ သို့မဟုတ် `big 250`, `s 50`, `lucky100` စသည်ဖြင့် ရိုက်ပါ။\n"
        "_ပွဲတစ်ပွဲတည်းမှာ မတူညီတဲ့ ရလဒ်တွေပေါ် အကြိမ်ပေါင်းများစွာ လောင်းကြေးထပ်နိုင်ပါတယ်။_ \n\n"
        "⏳ လောင်းကြေးများကို *စက္ကန့် ၆၀* အတွင်း ပိတ်ပါမည်! ကံကောင်းပါစေ!",
        parse_mode="Markdown", reply_markup=keyboard
    )
    logger.info(f"_start_interactive_game_round: Match {match_id} started successfully in chat {chat_id}. Betting open for 60 seconds.")

    context.job_queue.run_once(
        close_bets_scheduled,
        60, # seconds from now
        chat_id=chat_id,
        data=game
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
        await context.bot.send_message(
            chat_id,
            "🎉 *စီစဉ်ထားသောပွဲများ အားလုံး ပြီးဆုံးပါပြီ!* 🎉\n"
            "နောက်ဆုံးရမှတ်များကြည့်ရန် /leaderboard ကိုသုံးပါ။",
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
                "❌ အုပ်စုအုပ်ချုပ်သူစာရင်းကို ရယူ၍မရပါ။ ဘော့တ်တွင် 'ချတ်အုပ်ချုပ်သူများကို ရယူရန်' ခွင့်ပြုချက်ရှိကြောင်း သေချာပါစေ။ ထပ်မံကြိုးစားပါ။",
                parse_mode="Markdown"
            )
            return

    if not is_admin(chat_id, user_id):
        logger.warning(f"start_dice: User {user_id} is not an admin and tried to start a game in chat {chat_id}.")
        return await update.message.reply_text("❌ အုပ်ချုပ်သူများသာ အန်စာတုံးဂိမ်းအသစ်ကို စတင်နိုင်ပါသည်။", parse_mode="Markdown")

    current_game = context.chat_data.get("game")
    if current_game and current_game.state != GAME_OVER:
        logger.warning(f"start_dice: Game already active in chat {chat_id}. State: {current_game.state}")
        return await update.message.reply_text("⚠️ ဂိမ်းတစ်ခု စတင်ထားပြီးဖြစ်သည်။ ပြီးဆုံးရန် သို့မဟုတ် လက်ရှိပွဲပြီးဆုံးရန် စောင့်ဆိုင်းပေးပါ။", parse_mode="Markdown")
    
    if context.chat_data.get("num_matches_total") is not None:
         return await update.message.reply_text("⚠️ ပွဲစဉ်များ ဆက်တိုက်စတင်ထားပြီးဖြစ်သည်။ ပြီးဆုံးရန် စောင့်ဆိုင်းပေးပါ။", parse_mode="Markdown")


    num_matches_requested = 1

    if context.args:
        try:
            num_matches_requested = int(context.args[0])
            if num_matches_requested <= 0:
                return await update.message.reply_text("❌ ပွဲအရေအတွက်သည် ဂဏန်းအပြုသဘော (positive integer) ဖြစ်ရမည်။", parse_mode="Markdown")
            elif num_matches_requested > 20: 
                return await update.message.reply_text("❌ တစ်ကြိမ်တည်းတွင် ဆက်တိုက်အန်စာတုံးပွဲ ၂၀ ပွဲအထိသာ စီစဉ်နိုင်ပါသည်။", parse_mode="Markdown")
        except ValueError:
            await update.message.reply_text(
                "ℹ️ `/startdice` အတွက် မမှန်ကန်သော အကြောင်းပြချက်။ တစ်ပွဲတည်းသော အန်စာတုံးပွဲကို စတင်ပါမည်။\n"
                "အသုံးပြုပုံ: `/startdice` သည် တစ်ပွဲစတင်ရန်၊ သို့မဟုတ် `/startdice <အရေအတွက်>` သည် ဆက်တိုက်ပွဲများစွာအတွက်ဖြစ်သည်။",
                parse_mode="Markdown"
            )
            num_matches_requested = 1


    if num_matches_requested > 1:
        context.chat_data["num_matches_total"] = num_matches_requested
        context.chat_data["current_match_index"] = 0

        await update.message.reply_text(
            f"🎮 ဆက်တိုက် *{num_matches_requested}* ပွဲ ဆက်တိုက် အန်စာတုံး လောင်းကြေးပွဲများ စတင်တော့မည်။ ပထမပွဲအတွက် အဆင်သင့်ပြင်ထားပါ။",
            parse_mode="Markdown"
        )
        context.job_queue.run_once(
            _manage_game_sequence,
            2, # Small delay before first game starts
            chat_id=chat_id,
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
    if current_game_in_context is None or current_game_in_context != game:
        logger.warning(f"close_bets_scheduled: Skipping action for match {game.match_id} in chat {chat_id} as game instance changed or no game. Current game: {current_game_in_context.match_id if current_game_in_context else 'None'}.")
        return

    game.state = GAME_CLOSED
    logger.info(f"close_bets_scheduled: Bets closed for match {game.match_id} in chat {chat_id}. State set to GAME_CLOSED.")
    
    bet_summary_lines = [
        f"⏳ *ပွဲစဉ် #{game.match_id} အတွက် လောင်းကြေးများ ပိတ်ပါပြီ!* ⏳\n", 
        "*လက်ရှိလောင်းကြေးများ:*\n"
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
                bet_summary_lines.append(f"    → @{username_display}: *{amount}* pts")
    
    if not has_bets:
        bet_summary_lines.append("  ဤပွဲတွင် လောင်းကြေးထပ်ထားခြင်းမရှိပါ။")

    bet_summary_lines.append("\nအန်စာတုံးများကို လှိမ့်နေပါပြီ... အဆင်သင့်ပြင်ထားပါ။ 💥")
    
    try:
        logger.info(f"close_bets_scheduled: Attempting to send 'Bets closed and summary' message for match {game.match_id} to chat {chat_id}.")
        await context.bot.send_message(chat_id, "\n".join(bet_summary_lines), parse_mode="Markdown")
        logger.info(f"close_bets_scheduled: 'Bets closed and summary' message sent successfully for match {game.match_id}.")
    except Exception as e:
        logger.error(f"close_bets_scheduled: Error sending 'Bets closed' message for chat {chat_id}: {e}", exc_info=True)

    context.job_queue.run_once(
        roll_and_announce_scheduled,
        30, # seconds from now
        chat_id=chat_id,
        data=game
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
    winner_type, multiplier, individual_payouts = game.payout(chat_id)

    result_message_text = (
        f"🎉 *ပွဲစဉ် #{game.match_id} ရလဒ်များ ထွက်ပေါ်လာပါပြီ!* 🎉\n"
        f"🎲 *အန်စာတုံးလှိမ့်ခြင်း:* *{d1}* + *{d2}* = *{d1 + d2}* \n"
        f"🏆 *အနိုင်ရလောင်းကြေး:* *{winner_type.upper()}* {RESULT_EMOJIS[winner_type]} | *{multiplier} ဆ* ရရှိမည်\n\n"
        "*အသေးစိတ်ငွေထုတ်မှုများ:*\n"
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
                payout_lines.append(f"  ✨ @{username_display}: +*{winnings}* မှတ် (ရမှတ်အသစ်: *{player_info['score']}*)") # Translated points and New score
            else:
                payout_lines.append(f"  ✨ User ID {uid}: +*{winnings}* မှတ် (စာရင်းအင်းမတွေ့ပါ)") # Translated points and Stats not found
        result_message_text += "\n".join(payout_lines)
    else:
        result_message_text += "  ဒီအပတ်မှာ ဘယ်သူမှ မနိုင်ခဲ့ပါဘူး! နောက်တစ်ကြိမ် ကံကောင်းပါစေ။ 💔"

    lost_players = []
    for uid in game.participants:
        if uid not in individual_payouts:
            player_info = stats.get(uid)
            if player_info:
                username_display = player_info['username'].replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
                lost_players.append(f"  💀 @{username_display} (ရမှတ်: *{player_info['score']}*)") # Translated Score
            else:
                lost_players.append(f"  💀 User ID {uid} (ရမှတ်မတွေ့ပါ)") # Translated Score not found

    if lost_players:
        result_message_text += "\n\n*ကံစမ်းခဲ့ကြသူများ (နှင့် ရှုံးနိမ့်ခဲ့သူများ):*\n"
        result_message_text += "\n".join(lost_players)


    try:
        logger.info(f"roll_and_announce_scheduled: Attempting to send 'Results' message for match {game.match_id} to chat {chat_id}.")
        await context.bot.send_message(chat_id, result_message_text, parse_mode="Markdown")
        logger.info(f"roll_and_announce_scheduled: 'Results' message sent successfully for match {game.match_id}.")
    except Exception as e:
        logger.error(f"roll_and_announce_scheduled: Error sending 'Results' message for chat {chat_id}: {e}", exc_info=True)

    if context.chat_data.get("num_matches_total") is not None:
        logger.info(f"roll_and_announce_scheduled: Multi-match sequence active. Scheduling next game in sequence for chat {chat_id}.")
        context.job_queue.run_once(
            _manage_game_sequence,
            5, # 5-second delay before starting the next game
            chat_id=chat_id,
        )
    else:
        if "game" in context.chat_data:
            del context.chat_data["game"]
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
    
    # Escape username for Markdown
    username_escaped = username.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')

    game = context.chat_data.get("game")
    
    if not game:
        logger.info(f"button_callback: User {user_id} ({username}) tried to bet via button but no game active in chat {chat_id}.")
        return await query.message.reply_text(
            f"⚠️ @{username_escaped}, အန်စာတုံးဂိမ်း စတင်ထားခြင်း မရှိသေးပါ။ အုပ်ချုပ်သူတစ်ဦးက /startdice ဖြင့် စတင်ရန် လိုအပ်ပါသည်။", 
            parse_mode="Markdown"
        )
    
    if game.state != WAITING_FOR_BETS:
        logger.info(f"button_callback: User {user_id} ({username}) tried to bet via button but betting is closed for match {game.match_id} in chat {chat_id}. State: {game.state}")
        return await query.message.reply_text(
            f"⚠️ @{username_escaped}, ဤဂိမ်းအတွက် လောင်းကြေးများ ပိတ်လိုက်ပါပြီ။", 
            parse_mode="Markdown"
        )

    bet_type = data.split("_")[1]
    
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

    game = context.chat_data.get("game")
    if not game:
        logger.info(f"handle_bet: User {user_id} tried to place text bet but no game active in chat {chat_id}.")
        return await update.message.reply_text(
            f"⚠️ @{username_escaped}, အန်စာတုံးဂိမ်း စတင်ထားခြင်း မရှိသေးပါ။ အုပ်ချုပ်သူတစ်ဦးက /startdice ဖြင့် စတင်ရန် လိုအပ်ပါသည်။", 
            parse_mode="Markdown"
        )
    
    if game.state != WAITING_FOR_BETS:
        logger.info(f"handle_bet: User {user_id} ({username}) tried to place text bet but betting is closed for match {game.match_id} in chat {chat_id}. State: {game.state}")
        return await update.message.reply_text(
            f"⚠️ @{username_escaped}, ဤဂိမ်းအတွက် လောင်းကြေးများ ပိတ်လိုက်ပါပြီ။", 
            parse_mode="Markdown"
        )

    # Simplified regex for single bet parsing
    bet_match = re.match(r"^(big|b|small|s|lucky|l)\s*(\d+)$", message_text, re.IGNORECASE)

    if not bet_match:
        logger.warning(f"handle_bet: Invalid bet format for user {user_id} in message: '{message_text}' in chat {chat_id}.")
        return await update.message.reply_text(
            f"❌ @{username_escaped}, မမှန်ကန်သော လောင်းကြေးပုံစံ။ ကျေးဇူးပြု၍: `big 500`, `small 100`, `lucky 250` စသည်ဖြင့် ရိုက်ပါ။\n"
            "ဘတ်ခလုတ်များ (မူရင်း ၁၀၀ မှတ်) ကိုလည်း သုံးနိုင်သည်။",
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
        return await update.message.reply_text(f"❌ @{username_escaped}, လောင်းကြေးပမာဏသည် ဂဏန်းဖြစ်ရပါမည်။", parse_mode="Markdown")

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
            f"📊 သင့်ရမှတ်: *{player_stats['score']}* မှတ်\n" 
            f"✅ အနိုင်ရမှု: *{player_stats['wins']}* | ❌ ရှုံးနိမ့်မှု: *{player_stats['losses']}*", 
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "ℹ️ ဤချတ်တွင် ဂိမ်းများ မကစားရသေးပါ။ အုပ်ချုပ်သူတစ်ဦးကို /startdice ဖြင့် စတင်ရန် တောင်းဆိုပြီး မှတ်များရယူပါ။",
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
            f"👤 *@{username_display}* ၏ စာရင်းအင်းများ:\n" 
            f"  မှတ်များ: *{player_stats['score']}*\n" 
            f"  ကစားခဲ့သောပွဲများ: *{total_games}*\n" 
            f"  ✅ အနိုင်ရမှု: *{player_stats['wins']}*\n" 
            f"  ❌ ရှုံးနိမ့်မှု: *{player_stats['losses']}*\n" 
            f"  နိုင်ရနှုန်း: *{win_rate:.1f}%*\n" 
            f"  နောက်ဆုံးလှုပ်ရှားချိန်: *{player_stats['last_active'].strftime('%Y-%m-%d %H:%M')}*", 
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("ℹ️ သင့်အတွက် စာရင်းအင်းများ မတွေ့ရသေးပါ။ စတင်ကစားပြီး မှတ်တမ်းတင်ပါ။", parse_mode="Markdown")

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
        return await update.message.reply_text("ℹ️ ဤချတ်တွင် မှတ်တမ်းတင်ထားသော ကစားသမားများ မရှိသေးပါ။ ဂိမ်းစတင်ပြီး လောင်းကြေးထပ်ပါ။", parse_mode="Markdown")
    
    message_lines = ["🏆 *ထိပ်တန်းကစားသမားများ (ဦးဆောင်ဘုတ်):*\n"]
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
        await update.message.reply_text(f"Sorry, this bot is not authorized to run in this group ({chat_id}). Please add it to an allowed group.", parse_mode="Markdown")
        return
    # --- END Group ID check ---

    logger.info(f"history: User {update.effective_user.id} requested match history in chat {chat_id}")

    chat_specific_data = get_chat_data_for_id(chat_id)
    match_history_for_chat = chat_specific_data["match_history"] # Use chat-specific match_history
    
    if not match_history_for_chat:
        return await update.message.reply_text("ℹ️ ဤချတ်တွင် ပွဲမှတ်တမ်းများ မရှိသေးပါ။ မှတ်တမ်းများ ဖန်တမ်းရန် ဂိမ်းများ ကစားပါ။", parse_mode="Markdown")
    
    message_lines = ["📜 *မကြာသေးမီကပွဲများ (နောက်ဆုံး ၅ ပွဲ):*\n"]
    for match in match_history_for_chat[-5:][::-1]: 
        timestamp_str = match['timestamp'].strftime('%Y-%m-%d %H:%M')
        winner_display = match['winner'].upper().replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
        winner_emoji = RESULT_EMOJIS.get(match['winner'], '')
        
        message_lines.append(
            f"  • ပွဲစဉ် #{match['match_id']} | ရလဒ်: *{match['result']}* ({winner_display} {winner_emoji}) | ပါဝင်သူများ: *{match['participants']}* | အချိန်: {timestamp_str}" 
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
        return await update.message.reply_text("❌ အုပ်ချုပ်သူများသာ ကစားသမားရမှတ်များကို ချိန်ညှိနိုင်ပါသည်။", parse_mode="Markdown")

    target_user_id = None
    amount_to_adjust = None
    target_username_display = None

    if update.message.reply_to_message:
        if not context.args or len(context.args) != 1:
            return await update.message.reply_text(
                "❌ ပြန်ဖြေရာတွင် အသုံးပြုပုံ မမှန်ပါ။ ကျေးဇူးပြု၍: `/adjustscore <ပမာဏ>` ကိုသုံးပါ။\n"
                "ဥပမာ- အသုံးပြုသူ၏ မက်ဆေ့ချ်ကို ပြန်ဖြေပြီး `/adjustscore 500` (၅၀၀ မှတ် ထည့်ရန်) ဟု ရိုက်ပါ။",
                parse_mode="Markdown"
            )
        
        target_user_id = update.message.reply_to_message.from_user.id
        target_username_display = update.message.reply_to_message.from_user.username or update.message.reply_to_message.from_user.first_name
        
        try:
            amount_to_adjust = int(context.args[0])
        except ValueError:
            return await update.message.reply_text(
                "❌ ပမာဏ မမှန်ကန်ပါ။ ပမာဏသည် ဂဏန်းဖြစ်ကြောင်း သေချာပါစေ။\n"
                "ဥပမာ- အသုံးပြုသူ၏ မက်ဆေ့ချ်ကို ပြန်ဖြေပြီး `/adjustscore 500` ဟု ရိုက်ပါ။",
                parse_mode="Markdown"
            )

    elif context.args and len(context.args) >= 2:
        first_arg = context.args[0]
        try:
            amount_to_adjust = int(context.args[1])
        except ValueError:
            return await update.message.reply_text(
                "❌ ပမာဏ မမှန်ကန်ပါ။ ပမာဏသည် ဂဏန်းဖြစ်ကြောင်း သေချာပါစေ။\n"
                "ဥပမာ- `/adjustscore 123456789 500` သို့မဟုတ် `/adjustscore @someuser 100`။",
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
                        f"❌ အသုံးပြုသူ '@{mentioned_username}' ကို ဤချတ်၏ ဂိမ်းဒေတာတွင် မတွေ့ပါ။ ၎င်းတို့သည် ယခင်က ဘော့တ်နှင့် ဤချတ်တွင် အပြန်အလှန်တုံ့့ပြန်မှု ရှိခဲ့ရမည်။ တနည်းအားဖြင့် ၎င်းတို့၏ မက်ဆေ့ချ်တစ်ခုကို ပြန်ဖြေပါ သို့မဟုတ် ၎င်းတို့၏ ဂဏန်းအိုင်ဒီကို အသုံးပြုပါ။",
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
                    "❌ အသုံးပြုသူ အိုင်ဒီ (User ID) သို့မဟုတ် ပမာဏ မမှန်ပါ။ ကျေးဇူးပြု၍: `/adjustscore <user_id> <ပမာဏ>` သို့မဟုတ် `/adjustscore @username <ပမာဏ>` ကိုသုံးပါ။\n"
                    "ဥပမာ- `/adjustscore 123456789 500` သို့မဟုတ် `/adjustscore @someuser 100`။",
                    parse_mode="Markdown"
                )
            
    else: # Neither reply nor valid direct args
        return await update.message.reply_text(
            "❌ အသုံးပြုပုံ မမှန်ပါ။ ကျေးဇူးပြု၍ အောက်ပါတို့မှ တစ်ခုကို အသုံးပြုပါ။\n"
            "  - အသုံးပြုသူ၏ မက်ဆေ့ချ်ကို ပြန်ဖြေပါ: `/adjustscore <ပမာဏ>`\n"
            "  - တိုက်ရိုက်ထည့်သွင်းမှု: `/adjustscore <user_id> <ပမာဏ>`\n"
            "  - တိုက်ရိုက်ထည့်သွင်းမှု: `/adjustscore @username <ပမာဏ>`\n"
            "ဥပမာ- `/adjustscore 123456789 500` သို့မဟုတ် `/adjustscore @someuser 100`။",
            parse_mode="Markdown"
        )

    if target_user_id is None or amount_to_adjust is None:
        logger.error(f"adjust_score: Logic error: target_user_id ({target_user_id}) or amount_to_adjust ({amount_to_adjust}) is None after initial parsing. update_message: {update.message.text}")
        return await update.message.reply_text("❌ မမျှော်လင့်သော အမှားတစ်ခု ဖြစ်ပေါ်ခဲ့ပါသည်။ ကျေးဇူးပြု၍ ထပ်မံကြိုးစားပါ သို့မဟုတ် အကူအညီတောင်းပါ။", parse_mode="Markdown")

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
                f"❌ အိုင်ဒီ `{target_user_id}` ရှိ ကစားသမားကို ဤချတ်တွင် မတွေ့ရပါ။ Telegram က ၎င်းတို့၏ အသေးစိတ်အချက်အလက်များကို ရယူ၍မရပါ။ အသုံးပြုသူသည် ဤချတ်၏ အဖွဲ့ဝင်ဖြစ်ကြောင်း သေချာပါစေ သို့မဟုတ် ၎င်းတို့၏ မက်ဆေ့ချ်တစ်ခုကို ပြန်ဖြေကြည့်ပါ။",
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
        f"✅ @{username_display_escaped} (အိုင်ဒီ: `{target_user_id}`) ၏ ရမှတ်ကို *{amount_to_adjust}* မှတ် ချိန်ညှိပြီးပါပြီ။\n" 
        f"ယခင်ရမှတ်: *{old_score}* | ရမှတ်အသစ်: *{new_score}*။", 
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
        return await update.message.reply_text("❌ အုပ်ချုပ်သူများသာ အခြားကစားသမားများ၏ ရမှတ်များကို စစ်ဆေးနိုင်ပါသည်။", parse_mode="Markdown")

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
                        f"❌ အသုံးပြုသူ '@{mentioned_username}' ကို ဤချတ်၏ ဂိမ်းဒေတာတွင် မတွေ့ပါ။ ၎င်းတို့သည် ယခင်က ဘော့တ်နှင့် ဤချတ်တွင် အပြန်အလှန်တုံ့့ပြန်မှု ရှိခဲ့ရမည်။ တနည်းအားဖြင့် ၎င်းတို့၏ မက်ဆေ့ချ်တစ်ခုကို ပြန်ဖြေပါ သို့မဟုတ် ၎င်းတို့၏ ဂဏန်းအိုင်ဒီကို အသုံးပြုပါ။",
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
                    "❌ အသုံးပြုသူ အိုင်ဒီ (User ID) သို့မဟုတ် ပမာဏ မမှန်ပါ။ ကျေးဇူးပြု၍: `/checkscore <user_id>` သို့မဟုတ် `/checkscore @username` ကိုသုံးပါ။\n"
                    "ဥပမာ- `/checkscore 123456789` သို့မဟုတ် `/checkscore @someuser`။",
                    parse_mode="Markdown"
                )
    else:
        return await update.message.reply_text(
            "❌ အသုံးပြုပုံ မမှန်ပါ။ ကျေးဇူးပြု၍ အောက်ပါတို့မှ တစ်ခုကို အသုံးပြုပါ။\n"
            "  - အသုံးပြုသူ၏ မက်ဆေ့ချ်ကို ပြန်ဖြေပါ: `/checkscore`\n"
            "  - တိုက်ရိုက်ထည့်သွင်းမှု: `/checkscore <user_id>`\n"
            "  - တိုက်ရည့်ထည့်သွင်းမှု: `/checkscore @username`\n"
            "ဥပမာ- `/checkscore 123456789` သို့မဟုတ် `/checkscore @someuser`။",
            parse_mode="Markdown"
        )

    if target_user_id is None:
        logger.error(f"check_user_score: Logic error: target_user_id ({target_user_id}) is None after initial parsing. update_message: {update.message.text}")
        return await update.message.reply_text("❌ မမျှော်လင့်သော အမှားတစ်ခု ဖြစ်ပေါ်ခဲ့ပါသည်။ ကျေးဇူးပြု၍ ထပ်မံကြိုးစားပါ သို့မဟုတ် အကူအညီတောင်းပါ။", parse_mode="Markdown")

    chat_specific_data = get_chat_data_for_id(chat_id)
    player_stats = chat_specific_data["player_stats"].get(target_user_id)

    if not player_stats:
        try:
            chat_member = await context.bot.get_chat_member(chat_id, target_user_id)
            fetched_username = chat_member.user.username or chat_member.user.first_name
            username_display_escaped = fetched_username.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
            
            await update.message.reply_text(
                f"👤 *@{username_display_escaped}* (အိုင်ဒီ: `{target_user_id}`) တွင် ဤချတ်အတွက် ဂိမ်းစာရင်းအင်းများ မရှိသေးပါ။\n"
                f"၎င်းတို့၏ လက်ရှိရမှတ်မှာ *{INITIAL_PLAYER_SCORE}* မှတ် ဖြစ်သည်။",
                parse_mode="Markdown"
            )
            logger.info(f"check_user_score: Admin {requester_user_id} checked score for new user {target_user_id} (no stats yet).")
            return # Exit after informing user

        except Exception as e:
            logger.error(f"check_user_score: Failed to find player {target_user_id} or fetch their details in chat {chat_id}: {e}", exc_info=True)
            return await update.message.reply_text(
                f"❌ အိုင်ဒီ `{target_user_id}` ရှိ ကစားသမားကို ဤချတ်တွင် မတွေ့ရပါ။ Telegram က ၎င်းတို့၏ အသေးစိတ်အချက်အလက်များကို ရယူ၍မရပါ။ အသုံးပြုသူသည် ဤချတ်၏ အဖွဲ့ဝင်ဖြစ်ကြောင်း သေချာပါစေ သို့မဟုတ် ၎င်းတို့၏ မက်ဆေ့ချ်တစ်ခုကို ပြန်ဖြေကြည့်ပါ။",
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
        f"👤 *@{username_display_escaped}* ၏ စာရင်းအင်းများ (အိုင်ဒီ: `{target_user_id}`):\n"
        f"  မှတ်များ: *{player_stats['score']}*\n"
        f"  ကစားခဲ့သောပွဲများ: *{total_games}*\n"
        f"  ✅ အနိုင်ရမှု: *{player_stats['wins']}*\n"
        f"  ❌ ရှုံးနိမ့်မှု: *{player_stats['losses']}*\n"
        f"  နိုင်ရနှုန်း: *{win_rate:.1f}%*\n"
        f"  နောက်ဆုံးလှုပ်ရှားချိန်: *{player_stats['last_active'].strftime('%Y-%m-%d %H:%M')}*",
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
        return await update.message.reply_text("❌ အုပ်ချုပ်သူများသာ အုပ်ချုပ်သူစာရင်းကို အသစ်ပြန်တင်နိုင်ပါသည်။", parse_mode="Markdown")

    logger.info(f"refresh_admins: User {user_id} attempting to refresh admin list for chat {chat_id}.")
    
    if await update_group_admins(chat_id, context):
        await update.message.reply_text("✅ အုပ်ချုပ်သူစာရင်းကို အောင်မြင်စွာ အသစ်ပြန်တင်ပြီးပါပြီ။", parse_mode="Markdown")
    else:
        await update.message.reply_text(
            "❌ အုပ်ချုပ်သူစာရင်းကို အသစ်ပြန်တင်၍မရပါ။ ဘော့တ်တွင် 'ချတ်အုပ်ချုပ်သူများကို ရယူရန်' ခွင့်ပြုချက်ရှိကြောင်း သေချာပါစေ။",
            parse_mode="Markdown"
        )