from pathlib import Path

# Window configuration
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60
TITLE = "Kartouna"

# Paths
BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
IMAGES_DIR = ASSETS_DIR / "images"
SOUNDS_DIR = ASSETS_DIR / "sounds"
FONTS_DIR = ASSETS_DIR / "fonts"
BLENDER_EXPORTS_DIR = ASSETS_DIR / "blender_exports"

# Game setup
HAND_SIZE = 5
STARTING_TABLE_CARDS = 4

# AI setup
AI_ENABLED = True
AI_PLAYER_INDEX = 1
AI_DIFFICULTY = "medium"  # easy | medium | hard
AI_PLAY_DELAY = 0.65

# Card layout
CARD_WIDTH = 90
CARD_HEIGHT = 135
CARD_GAP = 20
TABLE_GAP = 18
MAX_TABLE_CARDS_PER_ROW = 8

# Animation timings (seconds)
PLAY_ANIMATION_TIME = 0.25
CAPTURE_ANIMATION_TIME = 0.40
DISTRIBUTION_ANIMATION_TIME = 0.45
HAND_ADJUST_ANIMATION_TIME = 0.18

# Color palette (Moroccan inspired)
DEEP_RED = (107, 24, 32)
DARK_RED = (57, 11, 17)
SAND = (229, 212, 177)
GOLD = (222, 178, 79)
LIGHT_GOLD = (246, 218, 146)
CREAM = (247, 240, 222)
EMERALD = (33, 120, 90)
BLACK = (22, 22, 22)
WHITE = (244, 244, 244)

# Screen states
STATE_MAIN_MENU = "main_menu"
STATE_DIFFICULTY_MENU = "difficulty_menu"
STATE_RULES = "rules"
STATE_PLAYING = "playing"
STATE_WINNER = "winner"

# Backward-compatible alias for older code.
STATE_MENU = STATE_MAIN_MENU
