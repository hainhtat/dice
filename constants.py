import os
from datetime import datetime # Import datetime for default values if needed

# Initial score for new players
INITIAL_PLAYER_SCORE = 0 # Default starting score changed to 0

# Global data storage: This will now hold a dictionary where keys are chat_ids,
# and values are dictionaries containing player_stats, match_history, group_admins,
# and a chat-specific match_counter.
global_data = {
    "all_chat_data": {} # Dictionary to hold all per-chat data
}

# Example structure for a single chat's data within "all_chat_data":
# "all_chat_data": {
#     chat_id_1: {
#         "match_counter": 1, # NOW PER-CHAT: Unique match counter for this specific chat
#         "player_stats": {
#             user_id_1: {"username": "UserA", "score": 0, "wins": 0, "losses": 0, "last_active": datetime.now()}, # Score now initializes to 0
#             user_id_2: {"username": "UserB", "score": 0, "wins": 1, "losses": 2, "last_active": datetime.now()}, # Score now initializes to 0
#         },
#         "match_history": [
#             {"match_id": 1, "result": 8, "winner": "big", "timestamp": datetime.now(), "participants": 2, "bets": {}},
#         ],
#         "group_admins": [] # List of admin user IDs for this specific chat
#     },
#     chat_id_2: {
#         "match_counter": 1,
#         "player_stats": {...},
#         "match_history": [...],
#         "group_admins": []
#     }
# }


# Hardcoded admin IDs (can be global for debugging or specific bot control)
# It's recommended to store sensitive IDs in environment variables for production.
HARDCODED_ADMINS = [
    # Example: int(os.environ.get("ADMIN_USER_ID_1")),
    # Add your personal Telegram User ID here for global admin access during testing
    # e.g., 123456789,
    1599213796,
    1846599182, # My user ID for testing
]
# Filter out None values and ensure they are integers in case env vars are not set or are invalid
HARDCODED_ADMINS = [int(x) for x in HARDCODED_ADMINS if isinstance(x, str) and x.isdigit() or isinstance(x, int)]


# Define a list of allowed group IDs
# IMPORTANT: Replace these with the actual chat IDs of your specific groups.
ALLOWED_GROUP_IDS = [
    -4859500151,
    -1002689980361, # This is an example group ID, REPLACE WITH YOUR ACTUAL GROUP ID
    # -1009876543210,  # Example Group ID 2
    # Add more group IDs as needed
]


# Emojis for dice game results
RESULT_EMOJIS = {
    "big": "🔼",
    "small": "�",
    "lucky": "🍀"
}
