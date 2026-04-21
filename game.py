from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

import pygame

from ai import choose_card_by_difficulty
from card import Card
from deck import Deck
from player import Player
from settings import (
    AI_DIFFICULTY,
    AI_ENABLED,
    AI_PLAY_DELAY,
    AI_PLAYER_INDEX,
    BLACK,
    CAPTURE_ANIMATION_TIME,
    CARD_GAP,
    CARD_HEIGHT,
    CARD_WIDTH,
    CREAM,
    DISTRIBUTION_ANIMATION_TIME,
    FPS,
    GOLD,
    HAND_ADJUST_ANIMATION_TIME,
    HAND_SIZE,
    LIGHT_GOLD,
    MAX_TABLE_CARDS_PER_ROW,
    PLAY_ANIMATION_TIME,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    STARTING_TABLE_CARDS,
    STATE_DIFFICULTY_MENU,
    STATE_MAIN_MENU,
    STATE_PLAYING,
    STATE_RULES,
    STATE_WINNER,
    TITLE,
    WHITE,
    TABLE_GAP,
)
from ui import (
    AssetManager,
    Button,
    draw_menu_background,
    draw_moroccan_background,
    draw_panel,
    draw_zellige_table,
)


@dataclass
class CardMoveAnimation:
    card: Card
    start_pos: pygame.Vector2
    end_pos: pygame.Vector2
    duration: float
    delay: float = 0.0
    elapsed: float = 0.0
    on_complete: Callable[[], None] | None = None

    def update(self, dt: float) -> bool:
        if self.delay > 0:
            self.delay = max(0.0, self.delay - dt)
            return False

        self.elapsed += dt
        progress = min(1.0, self.elapsed / max(self.duration, 0.0001))
        eased = 1.0 - ((1.0 - progress) ** 3)

        new_pos = self.start_pos.lerp(self.end_pos, eased)
        self.card.set_position((new_pos.x, new_pos.y))

        if progress >= 1.0:
            if self.on_complete:
                self.on_complete()
            return True
        return False


class Game:
    """Main game controller: screens, logic, rendering and turn flow."""

    def __init__(self) -> None:
        pygame.init()
        self.mixer_available = self._init_audio()

        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption(TITLE)

        self.clock = pygame.time.Clock()
        self.running = True

        self.assets = AssetManager(mixer_available=self.mixer_available)
        self.title_font = self.assets.get_font(78, bold=True)
        self.subtitle_font = self.assets.get_font(34, bold=True)
        self.button_font = self.assets.get_font(30, bold=True)
        self.text_font = self.assets.get_font(24)
        self.small_font = self.assets.get_font(20)
        self.card_font = self.assets.get_font(19, bold=True)

        self.state = STATE_MAIN_MENU
        self.time_since_start = 0.0
        self.victory_time = 0.0

        self.game_mode = "ai" if AI_ENABLED else "local"
        self.ai_enabled = self.game_mode == "ai"
        self.players: list[Player] = self._create_players_for_mode(self.game_mode)
        self.current_player_index = 0
        self.deck: Deck | None = None
        self.table_cards: list[Card] = []
        self.transient_cards: list[Card] = []
        self.animations: list[CardMoveAnimation] = []
        self.turn_locked = False
        self.last_capturer_index: int | None = None
        self.round_number = 0
        self.info_message = ""
        self.info_message_timer = 0.0
        self.ai_player_index = AI_PLAYER_INDEX if AI_PLAYER_INDEX in (0, 1) else 1
        self.ai_difficulty = self._normalize_ai_difficulty(AI_DIFFICULTY)
        self.ai_play_delay = max(0.0, AI_PLAY_DELAY)
        self.ai_think_timer = self.ai_play_delay

        self.winner_message = "Winner: Draw"

        self.menu_buttons: list[Button] = []
        self.difficulty_buttons: list[Button] = []
        self.rules_back_button: Button | None = None
        self.winner_buttons: list[Button] = []
        self.ui_layout: dict[str, int] = {}
        self._last_layout_size = self.screen.get_size()
        self._build_buttons()

        self.assets.play_music("moroccan_music.mp3", loops=-1)

    def _init_audio(self) -> bool:
        try:
            pygame.mixer.init()
            return True
        except pygame.error:
            return False

    def _menu_layout_values(self) -> dict[str, int]:
        width, height = self.screen.get_size()

        title_y = max(70, int(height * 0.11))
        subtitle_y = max(128, int(height * 0.19))
        button_height = max(56, min(68, int(height * 0.085)))
        button_gap = max(16, min(24, int(height * 0.028)))
        first_button_y = max(220, int(height * 0.33))

        main_button_width = min(460, max(320, int(width * 0.40)))
        secondary_button_width = min(360, max(260, int(width * 0.30)))

        return {
            "title_y": title_y,
            "subtitle_y": subtitle_y,
            "first_button_y": first_button_y,
            "button_height": button_height,
            "button_gap": button_gap,
            "main_button_width": main_button_width,
            "secondary_button_width": secondary_button_width,
            "rules_back_width": min(300, max(220, int(width * 0.24))),
            "rules_back_y": max(height - 70, int(height * 0.90)),
            "winner_buttons_y": max(390, int(height * 0.55)),
        }

    def create_menu_buttons(
        self,
        labels: list[str],
        start_y: int,
        button_width: int,
        button_height: int,
        gap: int,
        actions: list[str] | None = None,
    ) -> list[Button]:
        buttons: list[Button] = []
        button_x = (self.screen.get_width() // 2) - (button_width // 2)

        resolved_actions = (
            actions if actions is not None else [label.lower().replace(" ", "_") for label in labels]
        )

        for index, label in enumerate(labels):
            button_y = start_y + index * (button_height + gap)
            buttons.append(
                Button(
                    button_x,
                    button_y,
                    button_width,
                    button_height,
                    label,
                    resolved_actions[index],
                )
            )

        return buttons

    def _refresh_layout_if_needed(self) -> None:
        current_size = self.screen.get_size()
        if current_size == self._last_layout_size:
            return

        self._last_layout_size = current_size
        self._build_buttons()

    def _playing_layout_values(self) -> dict[str, int]:
        width, height = self.screen.get_size()

        score_panel_width = min(240, max(180, int(width * 0.18)))
        score_panel_height = max(66, min(82, int(height * 0.11)))
        score_panel_y = max(12, int(height * 0.02))

        turn_badge_width = min(460, max(320, int(width * 0.36)))
        turn_badge_height = max(62, min(76, int(height * 0.10)))
        turn_badge_y = score_panel_y

        top_ui_bottom = max(
            score_panel_y + score_panel_height,
            turn_badge_y + turn_badge_height,
        )

        top_hand_y = top_ui_bottom + 20
        bottom_hand_y = height - CARD_HEIGHT - 78
        instruction_badge_y = height - 56

        table_top = top_hand_y + CARD_HEIGHT + 20
        table_bottom = bottom_hand_y - 18
        table_height = max(170, table_bottom - table_top)
        table_y = table_bottom - table_height

        table_margin = max(120, int(width * 0.10))
        table_width = max(620, width - (table_margin * 2))

        return {
            "score_panel_width": score_panel_width,
            "score_panel_height": score_panel_height,
            "score_panel_y": score_panel_y,
            "score_left_x": 20,
            "score_right_x": width - score_panel_width - 20,
            "turn_badge_width": turn_badge_width,
            "turn_badge_height": turn_badge_height,
            "turn_badge_y": turn_badge_y,
            "top_hand_y": top_hand_y,
            "bottom_hand_y": bottom_hand_y,
            "instruction_badge_y": instruction_badge_y,
            "table_x": (width - table_width) // 2,
            "table_y": table_y,
            "table_width": table_width,
            "table_height": table_height,
            "info_message_y": turn_badge_y + turn_badge_height + 16,
        }

    def _build_buttons(self) -> None:
        self.ui_layout = self._menu_layout_values()

        button_width = self.ui_layout["main_button_width"]
        button_height = self.ui_layout["button_height"]
        gap = self.ui_layout["button_gap"]
        self.menu_buttons.clear()
        self.difficulty_buttons.clear()
        self.winner_buttons.clear()

        main_labels = [
            "Play Local 2 Players",
            "Play vs AI",
            "Rules",
            "Quit",
        ]
        main_actions = ["play_local", "play_ai_menu", "show_rules", "quit_game"]
        self.menu_buttons = self.create_menu_buttons(
            labels=main_labels,
            start_y=self.ui_layout["first_button_y"],
            button_width=button_width,
            button_height=button_height,
            gap=gap,
            actions=main_actions,
        )

        difficulty_labels = ["Easy", "Medium", "Hard", "Back"]
        difficulty_actions = ["ai_easy", "ai_medium", "ai_hard", "back_main"]
        self.difficulty_buttons = self.create_menu_buttons(
            labels=difficulty_labels,
            start_y=self.ui_layout["first_button_y"],
            button_width=self.ui_layout["secondary_button_width"],
            button_height=button_height,
            gap=gap,
            actions=difficulty_actions,
        )

        back_width = self.ui_layout["rules_back_width"]
        back_height = max(52, button_height - 4)
        back_x = (self.screen.get_width() // 2) - (back_width // 2)
        back_y = self.ui_layout["rules_back_y"] - (back_height // 2)
        self.rules_back_button = Button(back_x, back_y, back_width, back_height, "Main Menu", "main_menu")

        winner_labels = ["Play Again", "Main Menu", "Quit"]
        winner_actions = ["play_again", "main_menu", "quit_game"]
        self.winner_buttons = self.create_menu_buttons(
            labels=winner_labels,
            start_y=self.ui_layout["winner_buttons_y"],
            button_width=self.ui_layout["secondary_button_width"],
            button_height=max(52, button_height - 4),
            gap=max(12, gap - 4),
            actions=winner_actions,
        )

    def _normalize_ai_difficulty(self, difficulty: str) -> str:
        level = difficulty.lower().strip()
        if level in ("easy", "medium", "hard"):
            return level
        return "medium"

    def _create_players_for_mode(self, mode: str) -> list[Player]:
        top_name = "AI" if mode == "ai" else "Player 2"
        return [Player("Player 1", "bottom"), Player(top_name, "top")]

    def _back_to_main_menu(self) -> None:
        self.state = STATE_MAIN_MENU

    def _set_info_message(self, message: str, duration: float = 2.8) -> None:
        self.info_message = message
        self.info_message_timer = duration

    def _cards_to_deal_each_player(self) -> int:
        if self.deck is None:
            return 0

        remaining = self.deck.remaining()
        if remaining >= HAND_SIZE * 2:
            return HAND_SIZE

        # Final short deal to consume remaining cards equally and finish the deck.
        return remaining // 2

    def _apply_hand_combo_bonuses(self) -> list[str]:
        messages: list[str] = []
        for player in self.players:
            _, labels = player.apply_hand_combo_bonus()
            for label in labels:
                messages.append(f"{player.name}: {label}")
        return messages

    def _deal_round(
        self,
        include_table_cards: bool,
        cards_per_player: int | None = None,
    ) -> bool:
        if self.deck is None:
            return False

        if cards_per_player is None:
            cards_per_player = self._cards_to_deal_each_player()

        if cards_per_player <= 0:
            return False

        self.round_number += 1
        self.turn_locked = True

        deck_pos = self._deck_position()
        for player in self.players:
            new_cards = self.deck.draw(cards_per_player)
            player.receive_cards(new_cards)
            for card in new_cards:
                card.set_position(deck_pos)

        if include_table_cards:
            table_draw_count = min(STARTING_TABLE_CARDS, self.deck.remaining())
            for card in self.deck.draw(table_draw_count):
                card.set_owner("Table")
                card.set_position(deck_pos)
                self.table_cards.append(card)

        messages = self._apply_hand_combo_bonuses()
        if cards_per_player < HAND_SIZE:
            messages.append(f"Final deal: {cards_per_player} cards each")
        if messages:
            self._set_info_message(" | ".join(messages))

        self._animate_distribution(include_table=include_table_cards)
        return True

    def start_new_game(self, mode: str | None = None, difficulty: str | None = None) -> None:
        if mode is not None:
            self.game_mode = "ai" if mode == "ai" else "local"
        if difficulty is not None:
            self.ai_difficulty = self._normalize_ai_difficulty(difficulty)

        self.ai_enabled = self.game_mode == "ai"

        self.players = self._create_players_for_mode(self.game_mode)
        self.current_player_index = 0
        self.deck = Deck(self.assets)
        self.deck.shuffle()

        self.table_cards.clear()
        self.transient_cards.clear()
        self.animations.clear()
        self.turn_locked = False
        self.victory_time = 0.0
        self.last_capturer_index = None
        self.round_number = 0
        self.info_message = ""
        self.info_message_timer = 0.0
        self.ai_think_timer = self.ai_play_delay

        for player in self.players:
            player.reset_for_new_game()

        self._deal_round(include_table_cards=True, cards_per_player=HAND_SIZE)
        self.state = STATE_PLAYING

    def _is_ai_turn(self) -> bool:
        if not self.ai_enabled:
            return False
        if self.ai_player_index not in (0, 1):
            return False
        if self.state != STATE_PLAYING:
            return False
        if self.turn_locked:
            return False
        if self.current_player_index != self.ai_player_index:
            return False
        return self.players[self.ai_player_index].has_cards()

    def _play_ai_turn(self) -> None:
        if not self._is_ai_turn():
            return

        ai_player = self.players[self.ai_player_index]
        chosen_card = choose_card_by_difficulty(
            hand=ai_player.hand,
            table_cards=self.table_cards,
            difficulty=self.ai_difficulty,
        )
        if chosen_card is None:
            return

        try:
            hand_index = ai_player.hand.index(chosen_card)
        except ValueError:
            return

        self._set_info_message(
            f"{ai_player.name} ({self.ai_difficulty.title()}) played {chosen_card.value}",
            duration=1.4,
        )
        self._play_card(hand_index)

    def _deck_position(self) -> tuple[int, int]:
        return (SCREEN_WIDTH - CARD_WIDTH - 36, (SCREEN_HEIGHT // 2) - (CARD_HEIGHT // 2))

    def _hand_targets(self, player_index: int) -> list[tuple[int, int]]:
        cards = self.players[player_index].hand
        count = len(cards)
        if count == 0:
            return []

        total_width = (count * CARD_WIDTH) + ((count - 1) * CARD_GAP)
        width = self.screen.get_width()
        layout = self._playing_layout_values()
        start_x = (width - total_width) // 2
        y = layout["bottom_hand_y"] if player_index == 0 else layout["top_hand_y"]

        return [(start_x + index * (CARD_WIDTH + CARD_GAP), y) for index in range(count)]

    def _table_targets(self) -> list[tuple[int, int]]:
        count = len(self.table_cards)
        if count == 0:
            return []

        rows = (count + MAX_TABLE_CARDS_PER_ROW - 1) // MAX_TABLE_CARDS_PER_ROW
        total_height = (rows * CARD_HEIGHT) + ((rows - 1) * 14)
        start_y = (SCREEN_HEIGHT // 2) - (total_height // 2)

        targets: list[tuple[int, int]] = []
        for index in range(count):
            row = index // MAX_TABLE_CARDS_PER_ROW
            col = index % MAX_TABLE_CARDS_PER_ROW

            cards_in_this_row = min(
                MAX_TABLE_CARDS_PER_ROW, count - (row * MAX_TABLE_CARDS_PER_ROW)
            )
            row_width = (cards_in_this_row * CARD_WIDTH) + (
                (cards_in_this_row - 1) * TABLE_GAP
            )
            row_start_x = (SCREEN_WIDTH - row_width) // 2

            x = row_start_x + col * (CARD_WIDTH + TABLE_GAP)
            y = start_y + row * (CARD_HEIGHT + 14)
            targets.append((x, y))

        return targets

    def _table_center_target(self) -> tuple[int, int]:
        return ((SCREEN_WIDTH // 2) - (CARD_WIDTH // 2), (SCREEN_HEIGHT // 2) - (CARD_HEIGHT // 2))

    def _score_anchor(self, player_index: int) -> tuple[int, int]:
        if player_index == 0:
            return (210, SCREEN_HEIGHT - 70)
        return (210, 70)

    def _add_animation(
        self,
        card: Card,
        start: tuple[float, float] | pygame.Vector2,
        end: tuple[float, float] | pygame.Vector2,
        duration: float,
        delay: float = 0.0,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        animation = CardMoveAnimation(
            card=card,
            start_pos=pygame.Vector2(start),
            end_pos=pygame.Vector2(end),
            duration=duration,
            delay=delay,
            on_complete=on_complete,
        )
        self.animations.append(animation)

    def _animate_distribution(self, include_table: bool = True) -> None:
        bottom_targets = self._hand_targets(0)
        top_targets = self._hand_targets(1)
        table_targets = self._table_targets() if include_table else []

        order: list[tuple[Card, tuple[int, int]]] = []

        max_hand = max(len(self.players[0].hand), len(self.players[1].hand))
        for card_index in range(max_hand):
            if card_index < len(self.players[0].hand):
                order.append((self.players[0].hand[card_index], bottom_targets[card_index]))
            if card_index < len(self.players[1].hand):
                order.append((self.players[1].hand[card_index], top_targets[card_index]))

        if include_table:
            for index, card in enumerate(self.table_cards):
                order.append((card, table_targets[index]))

        pending = len(order)
        if pending == 0:
            self.turn_locked = False
            return

        def on_one_finished() -> None:
            nonlocal pending
            pending -= 1
            if pending <= 0:
                self.turn_locked = False

        for index, (card, target) in enumerate(order):
            self._add_animation(
                card=card,
                start=card.position,
                end=target,
                duration=DISTRIBUTION_ANIMATION_TIME,
                delay=index * 0.06,
                on_complete=on_one_finished,
            )

    def _layout_hand(self, player_index: int, animate: bool = False) -> None:
        hand = self.players[player_index].hand
        targets = self._hand_targets(player_index)

        for index, card in enumerate(hand):
            target = targets[index]
            if animate:
                self._add_animation(
                    card,
                    card.position,
                    target,
                    HAND_ADJUST_ANIMATION_TIME,
                )
            else:
                card.set_position(target)

    def _layout_table(self, animate: bool = False) -> None:
        targets = self._table_targets()
        for index, card in enumerate(self.table_cards):
            target = targets[index]
            if animate:
                self._add_animation(card, card.position, target, HAND_ADJUST_ANIMATION_TIME)
            else:
                card.set_position(target)

    def _try_play_card(self, mouse_pos: tuple[int, int]) -> None:
        if self.turn_locked:
            return

        player = self.players[self.current_player_index]

        for index in range(len(player.hand) - 1, -1, -1):
            card = player.hand[index]
            if card.is_clicked(mouse_pos):
                self._play_card(index)
                return

    def _play_card(self, hand_index: int) -> None:
        player = self.players[self.current_player_index]
        played_card = player.play_card(hand_index)
        if played_card is None:
            return

        self.assets.play_sound("card_click.wav")
        self.turn_locked = True

        self.transient_cards.append(played_card)
        self._layout_hand(self.current_player_index, animate=True)

        matching_cards = [card for card in self.table_cards if card.value == played_card.value]

        self._add_animation(
            card=played_card,
            start=played_card.position,
            end=self._table_center_target(),
            duration=PLAY_ANIMATION_TIME,
            on_complete=lambda: self._resolve_play(player, played_card, matching_cards),
        )

    def _resolve_play(self, player: Player, played_card: Card, matching_cards: list[Card]) -> None:
        if matching_cards:
            for table_card in matching_cards:
                if table_card in self.table_cards:
                    self.table_cards.remove(table_card)

            missa_bonus = 1 if len(self.table_cards) == 0 else 0
            if missa_bonus:
                player.add_bonus(missa_bonus)
                self._set_info_message(f"{player.name}: Missa +1")

            self.assets.play_sound("capture.wav")
            captured = [played_card] + matching_cards
            pending = len(captured)
            score_target = self._score_anchor(self.current_player_index)
            self.last_capturer_index = self.current_player_index

            def make_on_capture_done(card_obj: Card) -> Callable[[], None]:
                def _on_done() -> None:
                    nonlocal pending
                    if card_obj in self.transient_cards:
                        self.transient_cards.remove(card_obj)
                    player.capture([card_obj])
                    pending -= 1
                    if pending <= 0:
                        self._layout_table(animate=False)
                        self._finish_turn()

                return _on_done

            for index, captured_card in enumerate(captured):
                if captured_card not in self.transient_cards:
                    self.transient_cards.append(captured_card)

                offset_x = (index % 4) * 7
                offset_y = (index // 4) * 5
                destination = (score_target[0] + offset_x, score_target[1] + offset_y)

                self._add_animation(
                    card=captured_card,
                    start=captured_card.position,
                    end=destination,
                    duration=CAPTURE_ANIMATION_TIME,
                    delay=index * 0.03,
                    on_complete=make_on_capture_done(captured_card),
                )
        else:
            if played_card in self.transient_cards:
                self.transient_cards.remove(played_card)
            played_card.set_owner("Table")
            self.table_cards.append(played_card)
            self._layout_table(animate=False)
            self._finish_turn()

    def _finish_turn(self) -> None:
        if not self.players[0].has_cards() and not self.players[1].has_cards():
            cards_per_player = self._cards_to_deal_each_player()
            if cards_per_player > 0:
                # Next round starts with the opposite player for fair alternation.
                self.current_player_index = 1 - self.current_player_index
                self._deal_round(include_table_cards=False, cards_per_player=cards_per_player)
                return

            self._end_game()
            return

        self.current_player_index = 1 - self.current_player_index
        self.turn_locked = False

    def _collect_remaining_table_cards(self) -> None:
        if not self.table_cards:
            return

        if self.last_capturer_index is None:
            return

        collector = self.players[self.last_capturer_index]
        remaining_cards = self.table_cards[:]
        self.table_cards.clear()
        collector.capture(remaining_cards)

        self._set_info_message(
            f"{collector.name} collects remaining table cards",
            duration=3.2,
        )

    def _end_game(self) -> None:
        self._collect_remaining_table_cards()

        p1, p2 = self.players
        if p1.score > p2.score:
            self.winner_message = f"Winner: {p1.name}"
        elif p2.score > p1.score:
            self.winner_message = f"Winner: {p2.name}"
        else:
            self.winner_message = "Winner: Draw"

        self.assets.play_sound("win.wav")
        self.state = STATE_WINNER
        self.turn_locked = True
        self.victory_time = 0.0

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return

            if self.state == STATE_MAIN_MENU:
                self._handle_menu_event(event)
            elif self.state == STATE_DIFFICULTY_MENU:
                self._handle_difficulty_event(event)
            elif self.state == STATE_RULES:
                self._handle_rules_event(event)
            elif self.state == STATE_PLAYING:
                self._handle_playing_event(event)
            elif self.state == STATE_WINNER:
                self._handle_winner_event(event)

    def _handle_menu_event(self, event: pygame.event.Event) -> None:
        for button in self.menu_buttons:
            if button.handle_event(event):
                if button.action == "play_local":
                    self.start_new_game(mode="local")
                elif button.action == "play_ai_menu":
                    self.state = STATE_DIFFICULTY_MENU
                elif button.action == "show_rules":
                    self.state = STATE_RULES
                elif button.action == "quit_game":
                    self.running = False

    def _handle_difficulty_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._back_to_main_menu()
            return

        for button in self.difficulty_buttons:
            if button.handle_event(event):
                if button.action == "back_main":
                    self._back_to_main_menu()
                elif button.action == "ai_easy":
                    self.start_new_game(mode="ai", difficulty="easy")
                elif button.action == "ai_medium":
                    self.start_new_game(mode="ai", difficulty="medium")
                elif button.action == "ai_hard":
                    self.start_new_game(mode="ai", difficulty="hard")
                else:
                    self.start_new_game(mode="ai", difficulty="medium")

    def _handle_rules_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._back_to_main_menu()
            return

        if self.rules_back_button and self.rules_back_button.handle_event(event):
            self._back_to_main_menu()

    def _handle_playing_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._back_to_main_menu()
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._is_ai_turn():
                return
            self._try_play_card(event.pos)

    def _handle_winner_event(self, event: pygame.event.Event) -> None:
        for button in self.winner_buttons:
            if button.handle_event(event):
                if button.action == "play_again":
                    self.start_new_game()
                elif button.action == "main_menu":
                    self._back_to_main_menu()
                elif button.action == "quit_game":
                    self.running = False

    def update(self, dt: float) -> None:
        self.time_since_start += dt

        if self.state == STATE_WINNER:
            self.victory_time += dt

        if self.info_message_timer > 0:
            self.info_message_timer = max(0.0, self.info_message_timer - dt)
            if self.info_message_timer == 0:
                self.info_message = ""

        if self._is_ai_turn():
            self.ai_think_timer -= dt
            if self.ai_think_timer <= 0:
                self.ai_think_timer = self.ai_play_delay
                self._play_ai_turn()
        else:
            self.ai_think_timer = self.ai_play_delay

        finished: list[CardMoveAnimation] = []
        for animation in self.animations:
            if animation.update(dt):
                finished.append(animation)

        for animation in finished:
            if animation in self.animations:
                self.animations.remove(animation)

    def _draw_title(
        self,
        title: str,
        y: int,
        font: pygame.font.Font | None = None,
    ) -> None:
        title_font = font if font is not None else self.title_font
        center_x = self.screen.get_width() // 2

        shadow = title_font.render(title, True, BLACK)
        shadow_rect = shadow.get_rect(center=(center_x + 3, y + 3))
        self.screen.blit(shadow, shadow_rect)

        title_surface = title_font.render(title, True, LIGHT_GOLD)
        title_rect = title_surface.get_rect(center=(center_x, y))
        self.screen.blit(title_surface, title_rect)

    def _draw_menu_header(self, section_title: str) -> None:
        layout = self.ui_layout
        width, height = self.screen.get_size()

        title_font = self.assets.get_font(max(54, min(82, int(height * 0.11))), bold=True)
        subtitle_font = self.assets.get_font(max(24, min(34, int(height * 0.045))), bold=True)
        section_font = self.assets.get_font(max(20, min(30, int(height * 0.037))), bold=True)

        self._draw_title("Kartouna", layout["title_y"], title_font)

        subtitle = subtitle_font.render("Moroccan Ronda Card Game", True, CREAM)
        subtitle_rect = subtitle.get_rect(center=(width // 2, layout["subtitle_y"]))
        self.screen.blit(subtitle, subtitle_rect)

        section = section_font.render(section_title, True, LIGHT_GOLD)
        section_rect = section.get_rect(center=(width // 2, layout["subtitle_y"] + 40))
        self.screen.blit(section, section_rect)

        line_width = min(420, int(width * 0.34))
        line = pygame.Rect(0, 0, line_width, 2)
        line.center = (width // 2, layout["subtitle_y"] + 64)
        pygame.draw.rect(self.screen, GOLD, line)

    def _wrap_text_lines(
        self,
        text: str,
        font: pygame.font.Font,
        max_width: int,
    ) -> list[str]:
        words = text.split()
        if not words:
            return [""]

        lines: list[str] = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if font.size(candidate)[0] <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    def _draw_menu(self) -> None:
        width, height = self.screen.get_size()
        panel = pygame.Rect(0, 0, min(760, width - 160), min(620, height - 42))
        panel.center = (width // 2, height // 2)
        draw_panel(self.screen, panel, alpha=140)

        self._draw_menu_header("Main Menu")

        helper_font = self.assets.get_font(max(18, min(24, int(height * 0.03))))
        helper_text = helper_font.render("Choose how you want to play", True, LIGHT_GOLD)
        helper_rect = helper_text.get_rect(center=(width // 2, self.ui_layout["first_button_y"] - 24))
        self.screen.blit(helper_text, helper_rect)

        for button in self.menu_buttons:
            button.draw(self.screen, self.button_font)

    def _draw_difficulty_menu(self) -> None:
        width, height = self.screen.get_size()
        panel = pygame.Rect(0, 0, min(700, width - 180), min(610, height - 56))
        panel.center = (width // 2, height // 2)
        draw_panel(self.screen, panel, alpha=145)

        self._draw_menu_header("Choose AI Difficulty")

        info_font = self.assets.get_font(max(17, min(22, int(height * 0.028))))
        info = info_font.render(f"Selected level: {self.ai_difficulty.title()}", True, LIGHT_GOLD)
        info_rect = info.get_rect(center=(width // 2, self.ui_layout["first_button_y"] - 24))
        self.screen.blit(info, info_rect)

        for button in self.difficulty_buttons:
            button.draw(self.screen, self.button_font)

    def _draw_rules(self) -> None:
        width, height = self.screen.get_size()
        panel = pygame.Rect(0, 0, min(1090, width - 90), min(670, height - 40))
        panel.center = (width // 2, height // 2)
        draw_panel(self.screen, panel, alpha=165)

        self._draw_menu_header("Rules")

        rules = [
            "1. Deck: 40 cards (1-7, 10, 11, 12) in Dhab/Sif/Kasa/3ssa suits.",
            "2. Each round: deal 5 cards per player and place 4 cards on table (first round).",
            "3. Play turn by turn. Matching value captures all matching table cards + played card.",
            "4. Missa: if a capture empties the table, you gain +1 bonus point.",
            "5. Ronda (pair in hand) gives +1. Tringa (three same) gives +5.",
            "6. Four cards of same value in hand gives +10.",
            "7. When hands end, deal new cards while deck still has cards.",
            "8. Remaining table cards go to the last player who captured.",
            "9. Highest final score wins.",
            "10. Press ESC during the game to return to menu.",
        ]

        content_rect = pygame.Rect(
            panel.left + 52,
            self.ui_layout["subtitle_y"] + 84,
            panel.width - 104,
            panel.height - 210,
        )

        font_size = max(16, min(24, int(height * 0.03)))
        grouped_lines: list[list[str]] = []
        rule_font = self.assets.get_font(font_size)
        paragraph_gap = 8

        while font_size >= 15:
            rule_font = self.assets.get_font(font_size)
            grouped_lines = [
                self._wrap_text_lines(rule_line, rule_font, content_rect.width)
                for rule_line in rules
            ]
            line_count = sum(len(group) for group in grouped_lines)
            total_height = (line_count * rule_font.get_linesize()) + ((len(grouped_lines) - 1) * paragraph_gap)
            if total_height <= content_rect.height:
                break
            font_size -= 1

        y = content_rect.top
        for group in grouped_lines:
            for line in group:
                text = rule_font.render(line, True, WHITE)
                text_rect = text.get_rect(midleft=(content_rect.left, y + (rule_font.get_linesize() // 2)))
                self.screen.blit(text, text_rect)
                y += rule_font.get_linesize()
            y += paragraph_gap

        if self.rules_back_button:
            self.rules_back_button.draw(self.screen, self.button_font)

    def _draw_score_panels(self) -> None:
        layout = self._playing_layout_values()
        panel_w = layout["score_panel_width"]
        panel_h = layout["score_panel_height"]

        top_panel = pygame.Rect(
            layout["score_left_x"],
            layout["score_panel_y"],
            panel_w,
            panel_h,
        )
        bottom_panel = pygame.Rect(
            layout["score_right_x"],
            layout["score_panel_y"],
            panel_w,
            panel_h,
        )

        turn_panel = pygame.Rect(0, 0, layout["turn_badge_width"], layout["turn_badge_height"])
        turn_panel.midtop = (self.screen.get_width() // 2, layout["turn_badge_y"])

        draw_panel(self.screen, top_panel, alpha=162)
        draw_panel(self.screen, bottom_panel, alpha=162)
        draw_panel(self.screen, turn_panel, alpha=172)

        p1 = self.players[0]
        p2 = self.players[1]

        def draw_player_panel(rect: pygame.Rect, player: Player, label: str) -> None:
            title = self.small_font.render(label, True, LIGHT_GOLD)
            title_rect = title.get_rect(midleft=(rect.left + 14, rect.top + 18))
            self.screen.blit(title, title_rect)

            value_font = self.assets.get_font(29, bold=True)
            score_value = value_font.render(str(player.score), True, CREAM)
            score_rect = score_value.get_rect(midleft=(rect.left + 16, rect.centery + 6))
            self.screen.blit(score_value, score_rect)

            stats = self.small_font.render(
                f"H {len(player.hand)} | C {len(player.captured_cards)}",
                True,
                CREAM,
            )
            stats_rect = stats.get_rect(midright=(rect.right - 14, rect.centery + 6))
            self.screen.blit(stats, stats_rect)

        draw_player_panel(top_panel, p2, p2.name)
        draw_player_panel(bottom_panel, p1, p1.name)

        current = self.players[self.current_player_index]
        if self.turn_locked:
            turn_label = "Resolving move..."
        else:
            turn_label = f"Current Turn: {current.name}"

        turn_text = self.text_font.render(turn_label, True, LIGHT_GOLD)
        turn_rect = turn_text.get_rect(center=(turn_panel.centerx, turn_panel.centery))
        self.screen.blit(turn_text, turn_rect)

    def _draw_deck_placeholder(self) -> None:
        deck_x, deck_y = self._deck_position()
        shadow_rect = pygame.Rect(deck_x + 4, deck_y + 4, CARD_WIDTH, CARD_HEIGHT)
        top_rect = pygame.Rect(deck_x, deck_y, CARD_WIDTH, CARD_HEIGHT)

        pygame.draw.rect(self.screen, (30, 11, 14), shadow_rect, border_radius=10)
        pygame.draw.rect(self.screen, (117, 34, 42), top_rect, border_radius=10)
        pygame.draw.rect(self.screen, GOLD, top_rect, width=3, border_radius=10)

        count = self.deck.remaining() if self.deck else 0
        text = self.small_font.render(f"Deck {count}", True, CREAM)
        self.screen.blit(text, (deck_x + 11, deck_y + CARD_HEIGHT + 8))

    def _draw_cards(self) -> None:
        # Top player hand
        top_active = self.current_player_index == 1 and not self.turn_locked
        for card in self.players[1].hand:
            card.draw(self.screen, self.card_font, hidden=False, outlined=top_active)

        # Table cards
        for card in self.table_cards:
            card.draw(self.screen, self.card_font, hidden=False, outlined=False)

        # Bottom player hand
        bottom_active = self.current_player_index == 0 and not self.turn_locked
        for card in self.players[0].hand:
            card.draw(self.screen, self.card_font, hidden=False, outlined=bottom_active)

        # Animated cards that are currently moving independently
        for card in self.transient_cards:
            card.draw(self.screen, self.card_font, hidden=False, outlined=False)

    def _draw_playing(self) -> None:
        layout = self._playing_layout_values()

        table_panel = pygame.Rect(
            layout["table_x"],
            layout["table_y"],
            layout["table_width"],
            layout["table_height"],
        )
        draw_zellige_table(self.screen, table_panel, self.assets, self.time_since_start)

        self._draw_score_panels()
        self._draw_deck_placeholder()
        self._draw_cards()

        if self.info_message:
            info_surface = self.small_font.render(self.info_message, True, LIGHT_GOLD)
            info_rect = info_surface.get_rect(center=(self.screen.get_width() // 2, layout["info_message_y"]))
            self.screen.blit(info_surface, info_rect)

        if self._is_ai_turn():
            hint_text = f"AI ({self.ai_difficulty.title()}) is thinking..."
        elif self.game_mode == "ai":
            hint_text = "Your turn: click one card from your hand"
        else:
            hint_text = "Click one card from the active player hand"

        hint_badge = pygame.Rect(0, 0, min(620, self.screen.get_width() - 180), 44)
        hint_badge.center = (self.screen.get_width() // 2, layout["instruction_badge_y"])
        draw_panel(self.screen, hint_badge, alpha=170)

        hint = self.small_font.render(hint_text, True, WHITE)
        hint_rect = hint.get_rect(center=hint_badge.center)
        self.screen.blit(hint, hint_rect)

    def _draw_winner(self) -> None:
        width, height = self.screen.get_size()
        panel = pygame.Rect(0, 0, min(780, width - 180), min(640, height - 70))
        panel.center = (width // 2, height // 2)
        draw_panel(self.screen, panel, alpha=160)

        self._draw_menu_header("Winner")

        center = (width // 2, max(240, int(height * 0.39)))
        rings = pygame.Surface((width, height), pygame.SRCALPHA)
        for i in range(6):
            radius = 80 + (i * 23) + int(math.sin(self.victory_time * 2.8 + i) * 6)
            alpha = max(18, 70 - i * 8)
            pygame.draw.circle(rings, (226, 179, 74, alpha), center, radius, width=2)
        self.screen.blit(rings, (0, 0))

        pulse_size = max(40, int(56 + (math.sin(self.victory_time * 5.5) * 4)))
        winner_font = self.assets.get_font(pulse_size, bold=True)

        winner_text = winner_font.render(self.winner_message, True, LIGHT_GOLD)
        winner_rect = winner_text.get_rect(center=center)
        self.screen.blit(winner_text, winner_rect)

        score_text = (
            f"Final Score - {self.players[0].name}: {self.players[0].score} | "
            f"{self.players[1].name}: {self.players[1].score}"
        )

        score_font_size = max(18, min(32, int(height * 0.04)))
        score_font = self.assets.get_font(score_font_size, bold=True)
        score_line = score_font.render(score_text, True, CREAM)

        while score_font_size > 16 and score_line.get_width() > panel.width - 40:
            score_font_size -= 1
            score_font = self.assets.get_font(score_font_size, bold=True)
            score_line = score_font.render(score_text, True, CREAM)

        score_rect = score_line.get_rect(center=(width // 2, center[1] + 82))
        self.screen.blit(score_line, score_rect)

        for button in self.winner_buttons:
            button.draw(self.screen, self.button_font)

    def render(self) -> None:
        self._refresh_layout_if_needed()

        if self.state == STATE_PLAYING:
            draw_moroccan_background(self.screen, self.assets, self.time_since_start)
        else:
            draw_menu_background(self.screen, self.assets, self.time_since_start)

        if self.state == STATE_MAIN_MENU:
            self._draw_menu()
        elif self.state == STATE_DIFFICULTY_MENU:
            self._draw_difficulty_menu()
        elif self.state == STATE_RULES:
            self._draw_rules()
        elif self.state == STATE_PLAYING:
            self._draw_playing()
        elif self.state == STATE_WINNER:
            self._draw_winner()

        pygame.display.flip()

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            self._handle_events()
            self.update(dt)
            self.render()

        pygame.quit()
