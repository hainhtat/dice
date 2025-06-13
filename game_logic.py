import random
from datetime import datetime
import logging

# Configure logging for this module
logger = logging.getLogger(__name__)

# Import global_data and INITIAL_PLAYER_SCORE from constants.py
from constants import global_data, RESULT_EMOJIS, INITIAL_PLAYER_SCORE

# Game states
WAITING_FOR_BETS, GAME_CLOSED, GAME_OVER = range(3)

# Helper function to get or initialize chat-specific data (NOW RE-ENABLED for in-memory)
def get_chat_data_for_id(chat_id):
    """
    Ensures the data structure for a given chat_id exists within global_data['all_chat_data']
    and returns a reference to it.
    """
    chat_specific_data = global_data["all_chat_data"].setdefault(chat_id, {
        "match_counter": 1, # Initialize per-chat match counter here
        "player_stats": {},
        "match_history": [],
        "group_admins": []
    })
    # Ensure player_stats and match_history keys exist if they are not there
    chat_specific_data.setdefault("player_stats", {})
    chat_specific_data.setdefault("match_history", [])
    chat_specific_data.setdefault("group_admins", []) # Ensure group_admins is always a list
    return chat_specific_data

class DiceGame:
    """
    Represents a single instance of the dice game.
    Manages bets, dice rolls, and payouts for one match.
    """
    def __init__(self, match_id, chat_id):
        self.match_id = match_id
        self.chat_id = chat_id # Store chat_id for logging and context
        # Stores active bets: {bet_type: {user_id: total_amount_bet_on_this_type}}
        self.bets = {"big": {}, "small": {}, "lucky": {}} 
        self.state = WAITING_FOR_BETS # Current state of the game match
        self.result = None # Stores the dice roll result (sum of two dice)
        self.start_time = datetime.now() # Timestamp when the game started
        self.participants = set() # Set of user_ids who have placed at least one bet in this match
        logger.info(f"DiceGame __init__: Match {self.match_id} started in chat {self.chat_id}")

    # --- UPDATED: Removed chat_id from place_bet arguments ---
    def place_bet(self, user_id, username, bet_type, amount): 
        """
        Allows a user to place a bet on a specific bet type.
        Uses self.chat_id to access chat-specific data.
        Users can now place multiple bets on different types, or add to existing bets.
        """
        # Use self.chat_id directly as it's already available in the instance
        chat_specific_data = get_chat_data_for_id(self.chat_id) 
        player_stats = chat_specific_data["player_stats"] # Access player_stats from chat_specific_data

        # Ensure player entry exists for the user; initialize with default score if new
        player = player_stats.setdefault(user_id, {
            "username": username,
            "score": INITIAL_PLAYER_SCORE, # Use INITIAL_PLAYER_SCORE
            "wins": 0,
            "losses": 0,
            "last_active": datetime.now()
        })
        player["last_active"] = datetime.now() # Update last active time for the player

        if amount <= 0:
            logger.warning(f"place_bet: User {user_id} tried to bet an invalid amount ({amount}) in chat {self.chat_id}.")
            return False, "❌ Bet amount must be positive!"
        
        # New: Minimum bet limit check
        MIN_BET_AMOUNT = 100
        if amount < MIN_BET_AMOUNT:
            logger.warning(f"place_bet: User {user_id} tried to bet {amount} which is below minimum bet {MIN_BET_AMOUNT} in chat {self.chat_id}.")
            return False, f"❌ Minimum bet amount is *{MIN_BET_AMOUNT}* points!"

        if player["score"] < amount:
            logger.warning(f"place_bet: User {user_id} (score: {player['score']}) tried to bet {amount} with insufficient points in chat {self.chat_id}.")
            return False, f"❌ Insufficient points! You only have *{player['score']}* points."

        # Deduct the new bet amount from score
        player["score"] -= amount

        # Add or update the bet for the specified bet_type for this user
        current_bet_on_type = self.bets[bet_type].get(user_id, 0)
        self.bets[bet_type][user_id] = current_bet_on_type + amount
        
        self.participants.add(user_id) # Add user to the list of participants for this match
        logger.info(f"place_bet: User {user_id} placed {amount} on {bet_type} for match {self.match_id} in chat {self.chat_id}. Total on {bet_type}: {self.bets[bet_type][user_id]}.")
        
        # Escape markdown characters in username for display
        username_display_escaped = username.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')

        # Updated response message to include current total bet on that type and current score
        return True, (
            f"✅ @{username_display_escaped}, your bet placed on *{bet_type.upper()}* for *{amount}* points!\n"
            f"Your total bet on *{bet_type.upper()}*: *{self.bets[bet_type][user_id]}* points.\n"
            f"Your current score: *{player['score']}*."
        )
    # --- END UPDATED ---

    def determine_winner(self):
        """Determines the winning bet type based on the dice roll result."""
        if self.result == 7:
            return "lucky" # Exact 7
        elif self.result > 7:
            return "big" # Greater than 7
        else:
            return "small" # Less than 7

    def payout(self, chat_id):
        """
        Distributes points to winners and updates player stats (wins/losses).
        Handles multiple bets per user.
        """
        winner_type = self.determine_winner()
        winning_bets = self.bets.get(winner_type, {}) # Get bets for the winning type
        multiplier = 5 if winner_type == "lucky" else 2 # Payout multiplier

        stats = get_chat_data_for_id(chat_id)["player_stats"] # Get player stats for the chat
        match_history = get_chat_data_for_id(chat_id)["match_history"] # Get match_history for the chat

        # Check if any bets were placed at all in this specific game instance
        any_bets_placed = any(bool(bet_type_dict) for bet_type_dict in self.bets.values())

        if not any_bets_placed:
            # If no bets were placed for this game (likely an automatic match),
            # we just record the match history and don't process player scores.
            logger.info(f"payout: No bets placed for match {self.match_id} in chat {chat_id}. Skipping score adjustments for players.")
            # Record match details in history, but with no participants if no one actually bet
            match_history.append({
                "match_id": self.match_id,
                "result": self.result,
                "winner": winner_type,
                "timestamp": datetime.now(),
                "participants": 0, # No active bettors in this game
                "bets": {} # No bets to record
            })
            return winner_type, multiplier, {} # Return empty payouts as no bets were made


        # Proceed with normal payout if bets were placed
        if not stats:
            # This warning should now only appear if bets were placed but no global stats exist,
            # which is an unusual state if the bot is running correctly.
            logger.warning(f"payout: No player stats found for chat {chat_id} during payout for match {self.match_id}, despite bets being present. This might indicate an issue with player data initialization.")
            return winner_type, multiplier, {} 

        # Keep track of individual payouts for the message
        individual_payouts = {}

        # Process winners: Add points and update win count
        for uid, amount_bet in winning_bets.items():
            if uid in stats:
                winnings = amount_bet * multiplier
                stats[uid]["score"] += winnings
                stats[uid]["wins"] += 1
                stats[uid]["last_active"] = datetime.now()
                individual_payouts[uid] = winnings # Store for message
                logger.info(f"payout: User {uid} won {winnings} in match {self.match_id}. New score: {stats[uid]['score']}")
            else:
                logger.warning(f"payout: Winning user {uid} not found in player stats for chat {chat_id} during payout.")

        # Process losers: Update loss count for those who bet on non-winning types
        # A user might have bet on multiple types, including the winning one.
        # We only count a loss if ALL their bets were on losing types.
        for uid in self.participants:
            # Check if this user had any winning bets
            if uid not in winning_bets:
                # If not, check if they had any bets at all (i.e., they participated and lost)
                total_bet_by_user = sum(self.bets[bt].get(uid, 0) for bt in self.bets)
                if total_bet_by_user > 0 and uid in stats:
                    stats[uid]["losses"] += 1
                    logger.info(f"payout: User {uid} lost in match {self.match_id}. Current score: {stats[uid]['score']}")


        # Record match details in history
        match_history.append({
            "match_id": self.match_id,
            "result": self.result,
            "winner": winner_type,
            "timestamp": datetime.now(),
            "participants": len(self.participants),
            # Store bets for historical review (optional, convert user_ids to strings for JSON compatibility)
            "bets": {bt: {str(uid): amt for uid, amt in bets.items()} for bt, bets in self.bets.items()}
        })
        logger.info(f"payout: Match {self.match_id} payout completed. Winner: {winner_type}, Multiplier: {multiplier} in chat {self.chat_id}.")
        return winner_type, multiplier, individual_payouts # Return individual payouts for message
