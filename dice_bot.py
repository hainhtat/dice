#!/usr/bin/env python3
# dice_bot.py - Enhanced Dice Betting Game Bot

import os
import random
import logging
import json
from typing import Dict, Any

# <<< FIX 1: Import load_dotenv before using it.
from dotenv import load_dotenv
from telegram import Update

# <<< FIX 2: Modernization - Use the new asyncio-based Application builder.
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# --- Configuration ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# Ensure ADMINS are correctly parsed as integers
ADMIN_IDS_STR = os.getenv("TELEGRAM_ADMIN_IDS", "")
ADMINS = [int(id.strip()) for id in ADMIN_IDS_STR.split(",") if id.strip()]
INITIAL_POINTS = 1000
MAX_BET = 5000
DATA_FILE = "dice_bot_data.json" # <<< FIX 3: Data persistence file

# --- Game State ---
# These will be loaded from the file
users: Dict[int, Dict[str, Any]] = {}
leaderboard: Dict[int, int] = {}

# <<< FIX 3: Add functions for data persistence
def save_data():
    """Saves the current game state to a JSON file."""
    try:
        with open(DATA_FILE, "w") as f:
            json.dump({"users": users, "leaderboard": leaderboard}, f, indent=4)
        logger.info("Game data saved successfully.")
    except IOError as e:
        logger.error(f"Error saving data to {DATA_FILE}: {e}")

def load_data():
    """Loads game state from a JSON file if it exists."""
    global users, leaderboard
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                # JSON saves integer keys as strings, so we need to convert them back
                users = {int(k): v for k, v in data.get("users", {}).items()}
                leaderboard = {int(k): v for k, v in data.get("leaderboard", {}).items()}
                logger.info("Game data loaded successfully.")
    except (IOError, json.JSONDecodeError) as e:
        logger.error(f"Error loading data from {DATA_FILE}: {e}")
        # Start with fresh data if file is corrupt
        users = {}
        leaderboard = {}


class DiceGame:
    @staticmethod
    def get_username(update: Update) -> str:
        """Generate a display name for the user."""
        user = update.effective_user
        name_parts = []
        if user.first_name:
            name_parts.append(user.first_name)
        if user.last_name:
            name_parts.append(user.last_name)
        if not name_parts:
            name_parts.append(f"User_{user.id}")
        return " ".join(name_parts)

    @staticmethod
    def initialize_user(user_id: int, username: str) -> None:
        """Initialize a new user in the game."""
        if user_id not in users:
            users[user_id] = {
                "points": INITIAL_POINTS,
                "bets": {},
                "username": username,
                "wins": 0,
                "losses": 0,
            }
            logger.info(f"New user {username} ({user_id}) initialized with {INITIAL_POINTS} points.")

# <<< FIX 2: All handlers must now be async
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message on /start."""
    await update.message.reply_text(
        "🎲 Welcome to Dice Bet Game! 🎲\n\n"
        "**Commands:**\n"
        "`/startdice` - Start a new betting round\n"
        "`/b <amount>` - Bet on Big (8-12)\n"
        "`/s <amount>` - Bet on Small (2-6)\n"
        "`/l <amount>` - Bet on Lucky 7\n"
        "`/roll` - Roll the dice to end the round\n"
        "`/score` - Check your points and stats\n"
        "`/leaderboard` - Show the top players\n"
        "`/help` - Show this message again"
    )

async def start_dice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start a new betting round."""
    # <<< FIX 5: This loop is redundant if roll_dice clears bets. Removed for clarity.
    await update.message.reply_text(
        "💰 **New betting round started!**\n\n"
        "Place your bets now:\n"
        "▪️ `/b <amount>` - **Big** (8-12) pays 2x\n"
        "▪️ `/s <amount>` - **Small** (2-6) pays 2x\n"
        "▪️ `/l <amount>` - **Lucky 7** pays 5x\n\n"
        f"Example: `/b 100` (Max bet per type: {MAX_BET})"
    )

async def validate_bet(update: Update, amount: int) -> bool:
    """Validate the bet amount."""
    user_id = update.effective_user.id
    if user_id not in users:
        DiceGame.initialize_user(user_id, DiceGame.get_username(update))

    if amount <= 0:
        await update.message.reply_text("❌ Bet amount must be positive.")
        return False
    if amount > MAX_BET:
        await update.message.reply_text(f"❌ Maximum bet is {MAX_BET} points.")
        return False

    current_total_bet = sum(users[user_id].get("bets", {}).values())
    if users[user_id]["points"] < current_total_bet + amount:
        await update.message.reply_text(
            f"❌ You don't have enough points.\n"
            f"Current points: {users[user_id]['points']}\n"
            f"Already bet: {current_total_bet}\n"
            f"Attempted new bet: {amount}"
        )
        return False
    return True

async def place_bet(update: Update, context: ContextTypes.DEFAULT_TYPE, bet_type: str) -> None:
    """Handle bet placement."""
    user_id = update.effective_user.id
    username = DiceGame.get_username(update)
    DiceGame.initialize_user(user_id, username)

    if not context.args:
        await update.message.reply_text(f"❌ Usage: `/{bet_type[0]} <amount>`")
        return

    try:
        amount = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number for your bet.")
        return

    if not await validate_bet(update, amount):
        return

    # Check for existing bet of this type and overwrite/add
    users[user_id]["bets"][bet_type] = amount
    total_bet = sum(users[user_id]['bets'].values())
    
    await update.message.reply_text(
        f"✅ {username}, your bet on **{bet_type.capitalize()}** for `{amount}` points is placed.\n"
        f"Your total bet this round is now `{total_bet}` points."
    )
    logger.info(f"{username} ({user_id}) placed {bet_type} bet: {amount}")

async def roll_dice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Roll dice and calculate results."""
    active_players = {
        uid: data for uid, data in users.items()
        if data.get("bets") and sum(data["bets"].values()) > 0
    }

    if not active_players:
        await update.message.reply_text(
            "No one has placed any bets yet!\nUse `/b`, `/s`, or `/l` to join the round."
        )
        return

    dice1 = random.randint(1, 6)
    dice2 = random.randint(1, 6)
    total = dice1 + dice2

    result_msg = (
        f"🎲 **The dice are rolled!** 🎲\n\n"
        f"Result: `{dice1} + {dice2} = {total}`\n\n"
        "--- **Payouts** ---\n"
    )

    for user_id, data in active_players.items():
        username = data["username"]
        bets = data["bets"]
        total_bet = sum(bets.values())
        payout = 0

        # Determine winning condition
        if total > 7:
            payout = bets.get("big", 0) * 2
        elif total < 7:
            payout = bets.get("small", 0) * 2
        elif total == 7:
            payout = bets.get("lucky", 0) * 5

        net_change = payout - total_bet
        users[user_id]["points"] += net_change

        if net_change > 0:
            users[user_id]["wins"] += 1
            result_msg += f"🟢 {username} won `{net_change}` points!\n"
        elif net_change < 0:
            users[user_id]["losses"] += 1
            result_msg += f"🔴 {username} lost `{abs(net_change)}` points.\n"
        else:
            result_msg += f"🟡 {username} broke even.\n"
        
        result_msg += f"   New balance: `{users[user_id]['points']}`\n"
        
        # Clear bets for the next round
        users[user_id]["bets"] = {}

    await update.message.reply_text(result_msg)
    logger.info(f"Dice rolled: {total}. Results processed for {len(active_players)} players.")
    
    # Save data after every round
    save_data()

async def show_score(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show player's current score."""
    user_id = update.effective_user.id
    username = DiceGame.get_username(update)

    if user_id not in users:
        await update.message.reply_text(
            f"Welcome, {username}! You haven't played yet. Use `/startdice` to begin."
        )
        return

    user_data = users[user_id]
    wins = user_data.get('wins', 0)
    losses = user_data.get('losses', 0)
    total_games = wins + losses
    
    # <<< FIX 4: Corrected win rate calculation
    win_rate_str = "N/A"
    if total_games > 0:
        win_rate = (wins / total_games) * 100
        win_rate_str = f"{win_rate:.1f}%"

    await update.message.reply_text(
        f"📊 **{username}'s Stats**\n\n"
        f"💰 **Points:** `{user_data['points']}`\n"
        f"🏆 **Wins:** `{wins}`\n"
        f"😢 **Losses:** `{losses}`\n"
        f"📈 **Win Rate:** `{win_rate_str}`"
    )

async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display the current leaderboard."""
    # Update leaderboard from users dict to ensure it's current
    current_leaderboard = {uid: data['points'] for uid, data in users.items()}

    if not current_leaderboard:
        await update.message.reply_text("The leaderboard is empty. Play a round to get on it!")
        return

    sorted_players = sorted(
        current_leaderboard.items(),
        key=lambda item: item[1],
        reverse=True
    )[:10]  # Top 10

    leaderboard_msg = "🏆 **Top 10 Players** 🏆\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for rank, (user_id, points) in enumerate(sorted_players, 1):
        username = users.get(user_id, {}).get("username", f"User_{user_id}")
        medal = medals[rank - 1] if rank <= 3 else f"{rank}."
        leaderboard_msg += f"{medal} {username}: `{points}` points\n"

    await update.message.reply_text(leaderboard_msg)

async def adjust_score(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to adjust player scores."""
    user_id = update.effective_user.id
    if user_id not in ADMINS:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    if len(context.args) != 2:
        await update.message.reply_text("Usage: `/adjust <user_id> <amount>`")
        return

    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID or amount. Both must be numbers.")
        return

    if target_id not in users:
        await update.message.reply_text("❌ User not found. They must play at least one round first.")
        return

    users[target_id]["points"] += amount
    target_username = users[target_id]['username']
    
    await update.message.reply_text(
        f"✅ Score adjusted for **{target_username}** by `{amount}`.\n"
        f"New balance: `{users[target_id]['points']}`"
    )
    logger.info(f"Admin {user_id} adjusted {target_id}'s score by {amount}.")
    save_data()

def main() -> None:
    """Start the bot."""
    if not TOKEN:
        logger.error("FATAL: No bot token provided. Set TELEGRAM_BOT_TOKEN in your .env file or environment.")
        return

    # Load data from file at startup
    load_data()

    # <<< FIX 2: Use Application.builder() for modern setup
    application = Application.builder().token(TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CommandHandler("startdice", start_dice))
    application.add_handler(CommandHandler("roll", roll_dice))
    application.add_handler(CommandHandler("score", show_score))
    application.add_handler(CommandHandler("stats", show_score)) # Alias for score
    application.add_handler(CommandHandler("leaderboard", show_leaderboard))
    application.add_handler(CommandHandler("adjust", adjust_score))
    
    # Bet handlers using lambdas are fine, but ensure they are async
    application.add_handler(CommandHandler("b", lambda u, c: place_bet(u, c, "big")))
    application.add_handler(CommandHandler("s", lambda u, c: place_bet(u, c, "small")))
    application.add_handler(CommandHandler("l", lambda u, c: place_bet(u, c, "lucky")))

    logger.info("Bot is starting...")
    # Run the bot until the user presses Ctrl-C
    application.run_polling()

if __name__ == "__main__":
    main()