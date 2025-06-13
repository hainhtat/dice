import os
from datetime import datetime # Import datetime for default values if needed

# Initial score for new players
INITIAL_PLAYER_SCORE = 0 # Default starting score for all new players.

# Global data storage: This will now hold a dictionary where keys are chat_ids,
# and values are dictionaries containing player_stats, match_history, group_admins,
# and a chat-specific match_counter.
global_data = {
    "all_chat_data": {} # Dictionary to hold all per-chat data for game instances.
}

# --- NEW FUNCTION: get_chat_data_for_id ---
def get_chat_data_for_id(chat_id: int):
    """
    Retrieves or initializes the chat-specific data dictionary from global_data.
    This function centralizes access and ensures consistent initialization for each chat.
    """
    if chat_id not in global_data["all_chat_data"]:
        global_data["all_chat_data"][chat_id] = {
            "match_counter": 1,
            "player_stats": {},
            "match_history": [],
            "group_admins": []
        }
    return global_data["all_chat_data"][chat_id]
# --- END NEW FUNCTION ---


# Hardcoded admin IDs (can be global for debugging or specific bot control)
# It's recommended to store sensitive IDs in environment variables for production.
HARDCODED_ADMINS = [
    # Example: int(os.environ.get("ADMIN_USER_ID_1")),
    # Add your personal Telegram User ID here for global admin access during testing
    # e.g., 123456789,
]
# Filter out None values and ensure they are integers in case env vars are not set or are invalid
HARDCODED_ADMINS = [int(x) for x in HARDCODED_ADMINS if isinstance(x, str) and x.isdigit() or isinstance(x, int)]


# Emojis for results
RESULT_EMOJIS = {
    "big": "🔼",
    "small": "🔽",
    "lucky": "🍀"
}

# --- NEW: Allowed Group IDs for the bot ---
# IMPORTANT: Replace these with the actual integer IDs of the Telegram groups
# where you want your bot to be active. You can get a group's ID by
# - Sending /id to a bot like @userinfobot in your group, or
# - Forwarding a message from the group to @JsonDumpBot, or
# - Adding your bot to the group and checking its logs for the chat_id.
ALLOWED_GROUP_IDS = [
    # Example: -100123456789, # Replace with your actual group IDs
    -4859500151,
    -1002689980361,
]
# --- END NEW ---
