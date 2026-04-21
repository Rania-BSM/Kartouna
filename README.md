# Kartouna

Kartouna is a local 2-player Moroccan digital card game prototype inspired by La Ronda.
This project modernizes traditional gameplay with a Moroccan visual identity using Python + Pygame, and supports Blender-rendered 3D assets.

## Tech Stack
- Python
- Pygame (game logic, interface, animation, local gameplay)
- Blender (asset creation and render export)

## Features Included
- Main Menu screen
- Rules screen
- 2-player local gameplay screen
- Winner screen with final scores
- Turn-based card play
- Capture logic by matching card value
- 40-card Moroccan/Spanish-style deck (1-7, 10, 11, 12)
- Moroccan suits: Dhab, Sif, Kasa, 3ssa
- Real-time score updates
- Missa bonus (+1 when a capture empties the table)
- Hand combo bonuses:
   - Ronda (+1)
   - Tringa (+5)
   - Four-of-kind (+10)
- Multi-round redeal until no playable cards remain in deck
- Remaining table cards awarded to last capturing player at game end
- Smooth card animations:
  - distribution animation
  - play-to-table animation
  - capture-to-score animation
  - winner pulse animation
- Sound system with safe fallback (game runs even if files are missing)

## Project Structure

kartouna/
|-- main.py
|-- settings.py
|-- game.py
|-- card.py
|-- deck.py
|-- player.py
|-- ui.py
|-- online_server.py
|-- online_client.py
|-- assets/
|   |-- images/
|   |-- sounds/
|   |-- fonts/
|   |-- blender_exports/
|-- README.md

## Installation
1. Install Python 3.10+.
2. Install pygame:

pip install pygame

## Run
From the project folder:

python main.py

## Online 1v1 (Hidden Cards)
This mode lets you play 1v1 over network where each player only sees:
- their own hand,
- table cards,
- opponent hand count (not card values).

### 1. Start server (host machine)
python online_server.py --host 0.0.0.0 --port 5050

### 2. Player 1 connect
python online_client.py --host 127.0.0.1 --port 5050

### 3. Player 2 connect
python online_client.py --host SERVER_IP --port 5050

Replace SERVER_IP with the host public IP or LAN IP.

Notes:
- Server is authoritative: clients do not receive opponent card values.
- Only current-turn player can play.
- If one player disconnects, server closes the match.

## Game Rules (Implemented)
- Deck has 40 cards with values: 1, 2, 3, 4, 5, 6, 7, 10, 11, 12.
- Suits are: Dhab, Sif, Kasa, 3ssa.
- First round: 5 cards per player and 4 cards on table.
- Players play one card per turn.
- Matching value captures all table matches plus the played card.
- Missa: if capture empties table, player gains +1 bonus point.
- Ronda: two same-value cards in hand gives +1 point.
- Tringa: three same-value cards in hand gives +5 points.
- Four same-value cards in hand gives +10 points.
- When both hands end, new cards are dealt from deck and play continues.
- At game end, remaining table cards go to the last player who captured.
- Player with highest score wins.

## Controls
- Left click on a card from the active player hand to play it.
- Esc during game: return to Main Menu.
- Use on-screen buttons for navigation.
- In Main Menu, use the Mode button to switch between 1 vs 1 and 1 vs AI before starting.

## AI Opponent
Player 2 can be controlled by AI.

Configuration in settings.py:
- AI_ENABLED = True
- AI_PLAYER_INDEX = 1
- AI_DIFFICULTY = "medium"  # easy | medium | hard
- AI_PLAY_DELAY = 0.65

AI strategy behavior:
- Easy: random card from hand.
- Medium: random capturing card if possible, otherwise random card.
- Hard:
   - choose the card that captures the most table cards,
   - add priority for Missa opportunities,
   - if no capture is possible, play the lowest card value.

## Assets and Optional File Names
The game works without external assets by generating card visuals in code.
If you export Blender assets, place PNG files in assets/images or assets/blender_exports.

Suggested image names:
- menu_background.png  (used automatically for Main Menu background)
- moroccan_table.png
- zellige_background.png
- golden_frame.png
- moroccan_lantern.png
- card_back_moroccan.png
- card_model_render.png

If menu_background.png is missing, the game uses an internal Moroccan-style fallback background.

Suggested sound names (place in assets/sounds):
- card_click.wav
- capture.wav
- win.wav
- moroccan_music.mp3

Optional fonts (place in assets/fonts):
- Amiri-Regular.ttf
- NotoNaskhArabic-Regular.ttf
- EBGaramond-Regular.ttf

## Blender Asset List to Create
Create the following Blender assets:
1. Moroccan game table
2. 3D card model
3. Zellige background
4. Golden frame
5. Moroccan lantern
6. Card back design with Moroccan pattern

## Blender Export Workflow (PNG for Pygame)
1. Model each asset in Blender.
2. Add materials using deep red and gold palette.
3. Set camera framing for each asset.
4. Add area lights for clean highlights.
5. In Render Properties:
   - Use Eevee or Cycles
   - Enable Film > Transparent (for object-only PNGs)
6. In Output Properties:
   - File Format: PNG
   - Color: RGBA
   - Resolution: at least 1024x1024 (or 2048x2048 for detailed cards)
7. Render image.
8. Save render to assets/blender_exports.

For card art:
- Render card front and card back separately.
- Keep same aspect ratio for all cards.
- Use transparent background to layer cards cleanly in Pygame.

## Notes for Further Improvement
- Add advanced La Ronda-specific rules.
- Add CPU mode for single player.
- Replace generated card graphics with Blender-rendered final assets.
- Add polished transitions and particle effects.
