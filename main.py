import logging
import asyncio # Re-added asyncio for sleep (still needed for context.job_queue functions)
import re # Added for more flexible regex matching
import os # Added for environment variable access

from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ChatMemberHandler, ContextTypes, filters
)
from telegram import Update # Import Update for type hinting in handlers

# Import handlers and constants from local files
from handlers import start, start_dice, close_bets_scheduled, roll_and_announce_scheduled, button_callback, handle_bet, show_score, show_stats, leaderboard, history, adjust_score, check_user_score, on_chat_member_update, refresh_admins, stop_game # Added stop_game
from constants import global_data, HARDCODED_ADMINS, INITIAL_PLAYER_SCORE, ALLOWED_GROUP_IDS
# --- END REVERTED ---

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Handler for unhandled text messages (if it was present in your previous main.py)
async def unhandled_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Logs all text messages that are not handled by other specific handlers."""
    if update.message and update.message.text:
        logger.debug(f"Unhandled text message received: '{update.message.text}' from user {update.effective_user.id} in chat {update.effective_chat.id}")


def main():
    """
    The main function that sets up and runs the Telegram bot.
    Initializes the Application and registers all handlers.
    """
    # --- REVERTED: Removed Firebase Initialization code ---
    # Firebase initialization is currently paused.
    # The bot will now use in-memory data storage as before.
    # --- END REVERTED ---

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN") #for production
    # bot_token = "8187381656:AAHnNiWB0Z98uJ5qBvbaXCsNqHHOt1itlGg" for testing
    if not bot_token:
        logger.error("main: TELEGRAM_BOT_TOKEN environment variable not set!")
        raise ValueError("Bot token is not set. Please set the TELEGRAM_BOT_TOKEN environment variable.")
    
    # Initialize the Application with your bot token.
    application = ApplicationBuilder().token(bot_token).build()
    
    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("startdice", start_dice))
    application.add_handler(CommandHandler("score", show_score))
    application.add_handler(CommandHandler(["stats","mystats"], show_stats))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("history", history))
    application.add_handler(CommandHandler("adjustscore", adjust_score))
    application.add_handler(CommandHandler("checkscore", check_user_score))
    application.add_handler(CommandHandler("refreshadmins", refresh_admins))
    application.add_handler(CommandHandler("stop", stop_game)) # NEW: Added stop_game command handler

    # Register callback query handler for inline keyboard buttons (betting buttons)
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Register message handler for text-based bets.
    # We now filter for messages that match the bet regex
    bet_regex_pattern = re.compile(r"^(big|b|small|s|lucky|l)\s*(\d+)$", re.IGNORECASE)
    application.add_handler(MessageHandler(filters.Regex(bet_regex_pattern) & filters.TEXT, handle_bet))

    # Add a fallback handler for any text messages that are not commands or specific bets
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.Regex(bet_regex_pattern), # Ensure it doesn't catch bets
        unhandled_message
    ))

    # Register ChatMemberHandler to detect when the bot joins/leaves a chat
    # or when its permissions change, allowing it to update admin lists.
    application.add_handler(ChatMemberHandler(on_chat_member_update, ChatMemberHandler.CHAT_MEMBER))

    logger.info("main: Dice Game Bot started polling...")
    # Start the bot's polling loop. allowed_updates=Update.ALL_TYPES ensures all update types are received.
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

