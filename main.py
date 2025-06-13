import logging
import asyncio # Re-added asyncio for sleep
import re # Added for more flexible regex matching
import os # NEW: Import the os module to access environment variables

from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ChatMemberHandler, ContextTypes, filters
)
from telegram import Update # Import Update for type hinting in handlers

# Import handlers and constants from local files
from handlers import start, start_dice, close_bets_scheduled, roll_and_announce_scheduled, button_callback, handle_bet, show_score, show_stats, leaderboard, history, adjust_score, check_user_score, on_chat_member_update, refresh_admins
from constants import global_data, HARDCODED_ADMINS, INITIAL_PLAYER_SCORE, ALLOWED_GROUP_IDS # Import ALLOWED_GROUP_IDS from constants

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    """
    The main function that sets up and runs the Telegram bot.
    Initializes the Application and registers all handlers.
    """
    # --- UPDATED: Retrieve bot token from environment variable ---
    # It's crucial for security not to hardcode your bot token in the code.
    # We will set the TELEGRAM_BOT_TOKEN environment variable on the hosting platform.
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        logger.error("main: TELEGRAM_BOT_TOKEN environment variable not set!")
        raise ValueError("Bot token is not set. Please set the TELEGRAM_BOT_TOKEN environment variable.")
    
    application = ApplicationBuilder().token(bot_token).build()
    # --- END UPDATED ---
    
    # Register command handlers.
    # Filters are now handled internally within each handler function in handlers.py.
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("startdice", start_dice))
    application.add_handler(CommandHandler("score", show_score))
    application.add_handler(CommandHandler(["stats","mystats"], show_stats))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("history", history))
    application.add_handler(CommandHandler("adjustscore", adjust_score))
    application.add_handler(CommandHandler("checkscore", check_user_score))
    application.add_handler(CommandHandler("refreshadmins", refresh_admins))

    # Register callback query handler for inline keyboard buttons (betting buttons).
    # Filters are now handled internally within button_callback function.
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Register message handler for text-based bets.
    # This regex is specifically for single bet commands to avoid being chatty.
    bet_regex_pattern = re.compile(r"^(big|b|small|s|lucky|l)\s*(\d+)$", re.IGNORECASE)
    application.add_handler(MessageHandler(filters.Regex(bet_regex_pattern) & filters.TEXT, handle_bet))


    # Register ChatMemberHandler.
    # This handler typically handles updates for the bot itself (e.g., being added/removed from groups).
    # The group filtering is applied *inside* on_chat_member_update if you want to restrict
    # its response to allowed groups, or removed if you want it to acknowledge all joins/leaves.
    application.add_handler(ChatMemberHandler(on_chat_member_update, ChatMemberHandler.CHAT_MEMBER))

    logger.info("main: Dice Game Bot started polling...")
    # Start the bot's polling loop. allowed_updates=Update.ALL_TYPES ensures all update types are received.
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

