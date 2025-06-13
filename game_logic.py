import random
from datetime import datetime
import logging

# Configure logging for this module
logger = logging.getLogger(__name__)

# Import global_data and INITIAL_PLAYER_SCORE, and get_chat_data_for_id from constants.py
from constants import global_data, RESULT_EMOJIS, INITIAL_PLAYER_SCORE, get_chat_data_for_id

# Game states represented by integers for clear, consistent state management
WAITING_FOR_BETS, GAME_CLOSED, GAME_OVER = range(3)

class DiceGame:
    """
    Represents a single instance of the dice game for a specific chat.
    Manages bets, dice rolls, and payouts for one match, and keeps track of game state.
    """
    def __init__(self, match_id: int, chat_id: int):
        self.match_id = match_id
        self.chat_id = chat_id # Store chat_id for logging and context
        # Stores active bets: {bet_type: {user_id: total_amount_bet_on_this_type}}
        # e.g., {"big": {12345: 500, 67890: 200}, "small": {}, "lucky": {12345: 100}}
        self.bets = {"big": {}, "small": {}, "lucky": {}} 
        self.state = WAITING_FOR_BETS # Initialize game state to allow betting
        self.result = None # Stores the sum of the two dice rolled (e.g., 7, 10, 4)
        self.start_time = datetime.now() # Timestamp when this specific match started
        # Set of user_ids who have placed at least one bet in this match, used for tracking participants
        self.participants = set() 
        logger.info(f"DiceGame __init__: Match {self.match_id} initialized for chat {self.chat_id}")

    def place_bet(self, user_id: int, username: str, bet_type: str, amount: int) -> tuple[bool, str]:
        """
        Allows a user to place a bet on a specific bet type (big, small, lucky).
        Users can place multiple bets on different types or add to existing bets on the same type.
        
        Args:
            user_id (int): The Telegram user ID of the player placing the bet.
            username (str): The username or first name of the player.
            bet_type (str): The type of bet ("big", "small", or "lucky").
            amount (int): The amount of points the user wishes to bet.
        
        Returns:
            tuple[bool, str]: A tuple containing:
                - bool: True if the bet was successfully placed, False otherwise.
                - str: A message indicating the outcome of the bet placement.
        """
        # Retrieve or initialize player stats for the specific chat using the centralized function
        chat_data = get_chat_data_for_id(self.chat_id)
        player_stats = chat_data["player_stats"]
        
        # Ensure player entry exists for the user; initialize with default score if new
        player = player_stats.setdefault(user_id, {
            "username": username,
            "score": INITIAL_PLAYER_SCORE,
            "wins": 0,
            "losses": 0,
            "last_active": datetime.now() # Update last active time when any action occurs
        })
        player["last_active"] = datetime.now() # Update last active time for the player

        # Validate bet amount
        if amount <= 0:
            logger.warning(f"place_bet: User {user_id} tried to bet an invalid amount ({amount}) in chat {self.chat_id}.")
            return False, "❌ လောင်းကြေးပမာဏသည် အပေါင်းကိန်းဖြစ်ရမည်!" # Bet amount must be positive!
        
        MIN_BET_AMOUNT = 100 # Define minimum bet amount
        if amount < MIN_BET_AMOUNT:
            logger.warning(f"place_bet: User {user_id} tried to bet {amount} which is below minimum bet {MIN_BET_AMOUNT} in chat {self.chat_id}.")
            return False, f"❌ အနည်းဆုံးလောင်းကြေးပမာဏမှာ *{MIN_BET_AMOUNT}* မှတ် ဖြစ်သည်!" # Minimum bet amount is {MIN_BET_AMOUNT} points!

        # Check if player has sufficient points
        if player["score"] < amount:
            logger.warning(f"place_bet: User {user_id} (score: {player['score']}) tried to bet {amount} with insufficient points in chat {self.chat_id}.")
            return False, f"❌ @{username} ရေ၊ ရမှတ်မလုံလောက်ပါဘူးရှင့်။ သင့်မှာ *{player_stats['score']}* မှတ်ပဲရှိတာနော်။" # Insufficient points! You only have {score} points.

        # Deduct the new bet amount from the player's score
        player["score"] -= amount

        # Add or update the bet for the specified bet_type for this user
        current_bet_on_type = self.bets[bet_type].get(user_id, 0)
        self.bets[bet_type][user_id] = current_bet_on_type + amount
        
        self.participants.add(user_id) # Add user to the set of participants for this match
        logger.info(f"place_bet: User {user_id} placed {amount} on {bet_type} for match {self.match_id} in chat {self.chat_id}. Total on {bet_type}: {self.bets[bet_type][user_id]}.")
        
        # Escape markdown characters in username for display in Telegram
        username_display_escaped = username.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')

        # Return success message with updated information
        return True, (
            f"✅ @{username_display_escaped}, သင်၏ လောင်းကြေး *{amount}* မှတ်ကို *{bet_type.upper()}* တွင် ထည့်သွင်းလိုက်ပါပြီ!\n"
            f"*{bet_type.upper()}* တွင် သင်၏ စုစုပေါင်းလောင်းကြေး: *{self.bets[bet_type][user_id]}* မှတ်။\n"
            f"သင့်လက်ရှိရမှတ်: *{player['score']}* မှတ်။"
        )

    def determine_winner(self) -> str:
        """
        Determines the winning bet type based on the dice roll result (self.result).
        
        Returns:
            str: The winning bet type ("big", "small", or "lucky").
        """
        if self.result == 7:
            return "lucky" # Exact 7 for the highest payout
        elif self.result > 7:
            return "big" # Greater than 7
        else:
            return "small" # Less than 7

    def payout(self, chat_id: int) -> tuple[str, int, dict]:
        """
        Distributes points to winners based on their bets and updates player statistics.
        Handles individual payouts and updates win/loss counts.
        
        Args:
            chat_id (int): The ID of the chat where the game is being played.
            
        Returns:
            tuple[str, int, dict]: A tuple containing:
                - str: The winning bet type.
                - int: The multiplier applied to winning bets.
                - dict: A dictionary of individual payouts {user_id: winnings_amount}.
        """
        winner_type = self.determine_winner()
        winning_bets = self.bets.get(winner_type, {}) # Get bets placed on the winning type
        multiplier = 5 if winner_type == "lucky" else 2 # Determine payout multiplier

        # Retrieve player stats for the specific chat
        chat_data = get_chat_data_for_id(chat_id)
        player_stats = chat_data["player_stats"]

        # Check if any bets were placed at all in this specific game instance
        any_bets_placed = any(bool(bet_type_dict) for bet_type_dict in self.bets.values())

        if not any_bets_placed:
            logger.info(f"payout: No bets placed for match {self.match_id} in chat {chat_id}. Skipping score adjustments for players.")
            # Record match history with no participants if no bets were made
            chat_data["match_history"].append({
                "match_id": self.match_id,
                "result": self.result,
                "winner": winner_type,
                "timestamp": datetime.now(),
                "participants": 0, # No active bettors in this game
                "bets": {} # No bets to record
            })
            return winner_type, multiplier, {} # Return empty payouts as no bets were made


        # Proceed with normal payout if bets were placed
        if not player_stats:
            logger.warning(f"payout: No player stats found for chat {chat_id} during payout for match {self.match_id}, despite bets being present. This might indicate an issue with player data initialization.")
            return winner_type, multiplier, {} 

        # Dictionary to store individual payouts for the result message
        individual_payouts = {}

        # Process winners: Add points and update win count
        for uid, amount_bet in winning_bets.items():
            if uid in player_stats:
                winnings = amount_bet * multiplier
                player_stats[uid]["score"] += winnings
                player_stats[uid]["wins"] += 1
                player_stats[uid]["last_active"] = datetime.now() # Update last active time
                individual_payouts[uid] = winnings # Store for result message
                logger.info(f"payout: User {uid} won {winnings} in match {self.match_id}. New score: {player_stats[uid]['score']}")
            else:
                logger.warning(f"payout: Winning user {uid} not found in player stats for chat {chat_id} during payout.")

        # Process losers: Update loss count for those who bet on non-winning types
        # A user is considered a loser if they participated in the game (placed any bet)
        # but did not have any winning bets for this round.
        for uid in self.participants:
            if uid not in winning_bets: # If this user did not bet on the winning type
                # Check if they had any bets at all (i.e., they participated and lost)
                total_bet_by_user = sum(self.bets[bt].get(uid, 0) for bt in self.bets)
                if total_bet_by_user > 0 and uid in player_stats:
                    player_stats[uid]["losses"] += 1
                    logger.info(f"payout: User {uid} lost in match {self.match_id}. Current score: {player_stats[uid]['score']}")

        # Record match details in history for the specific chat
        chat_data["match_history"].append({
            "match_id": self.match_id,
            "result": self.result,
            "winner": winner_type,
            "timestamp": datetime.now(),
            "participants": len(self.participants),
            # Store bets for historical review (convert user_ids to strings for easier JSON compatibility if needed)
            "bets": {bt: {str(uid): amt for uid, amt in bets.items()} for bt, bets in self.bets.items()}
        })
        logger.info(f"payout: Match {self.match_id} payout completed. Winner: {winner_type}, Multiplier: {multiplier} in chat {self.chat_id}.")
        return winner_type, multiplier, individual_payouts # Return individual payouts for message
