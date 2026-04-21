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
    STATE_MENU,
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

        self.state = STATE_MENU
        self.time_since_start = 0.0
        self.victory_time = 0.0

        self.players: list[Player] = [
            Player("Player 1", "bottom"),
            Player("Player 2", "top"),
        ]
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
        self.ai_enabled = AI_ENABLED
        self.ai_player_index = AI_PLAYER_INDEX if AI_PLAYER_INDEX in (0, 1) else 1
        self.ai_difficulty = AI_DIFFICULTY
        self.ai_play_delay = max(0.0, AI_PLAY_DELAY)
        self.ai_think_timer = self.ai_play_delay
        self.selected_mode = "1vsAI" if self.ai_enabled else "1vs1"

        self.winner_message = "Winner: Draw"

        self.menu_buttons: list[Button] = []
        self.mode_button: Button | None = None
        self.rules_back_button: Button | None = None
        self.winner_buttons: list[Button] = []
        self._build_buttons()

        self.assets.play_music("moroccan_music.mp3", loops=-1)

    def _init_audio(self) -> bool:
        try:
            pygame.mixer.init()
            return True
        except pygame.error:
            return False

    def _build_buttons(self) -> None:
        button_width = 300
        button_height = 62
        gap = 18
        self.menu_buttons.clear()
        self.winner_buttons.clear()

        first_y = 275

        start_rect = pygame.Rect(0, 0, button_width, button_height)
        start_rect.center = (SCREEN_WIDTH // 2, first_y)
        self.menu_buttons.append(Button(start_rect, "Start Game"))

        mode_rect = pygame.Rect(0, 0, button_width, button_height)
        mode_rect.center = (SCREEN_WIDTH // 2, first_y + (button_height + gap))
        self.mode_button = Button(mode_rect, self._mode_button_label())
        self.menu_buttons.append(self.mode_button)

        rules_rect = pygame.Rect(0, 0, button_width, button_height)
        rules_rect.center = (SCREEN_WIDTH // 2, first_y + 2 * (button_height + gap))
        self.menu_buttons.append(Button(rules_rect, "Rules"))

        quit_rect = pygame.Rect(0, 0, button_width, button_height)
        quit_rect.center = (SCREEN_WIDTH // 2, first_y + 3 * (button_height + gap))
        self.menu_buttons.append(Button(quit_rect, "Quit"))

        back_rect = pygame.Rect(0, 0, 220, 56)
        back_rect.center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 80)
        self.rules_back_button = Button(back_rect, "Main Menu")

        winner_labels = ["Play Again", "Main Menu", "Quit"]
        first_y = 470
        for index, label in enumerate(winner_labels):
            rect = pygame.Rect(0, 0, 260, 56)
            rect.center = (
                SCREEN_WIDTH // 2,
                first_y + index * (56 + 12),
            )
            self.winner_buttons.append(Button(rect, label))

    def _mode_button_label(self) -> str:
        return "Mode: 1 vs AI" if self.selected_mode == "1vsAI" else "Mode: 1 vs 1"

    def _toggle_mode(self) -> None:
        if self.selected_mode == "1vsAI":
            self.selected_mode = "1vs1"
        else:
            self.selected_mode = "1vsAI"

        if self.mode_button:
            self.mode_button.label = self._mode_button_label()

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

    def start_new_game(self) -> None:
        self.ai_enabled = self.selected_mode == "1vsAI"

        self.players = [Player("Player 1", "bottom"), Player("Player 2", "top")]
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
        start_x = (SCREEN_WIDTH - total_width) // 2
        y = SCREEN_HEIGHT - CARD_HEIGHT - 30 if player_index == 0 else 30

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
            self.winner_message = "Winner: Player 1"
        elif p2.score > p1.score:
            self.winner_message = "Winner: Player 2"
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

            if self.state == STATE_MENU:
                self._handle_menu_event(event)
            elif self.state == STATE_RULES:
                self._handle_rules_event(event)
            elif self.state == STATE_PLAYING:
                self._handle_playing_event(event)
            elif self.state == STATE_WINNER:
                self._handle_winner_event(event)

    def _handle_menu_event(self, event: pygame.event.Event) -> None:
        for button in self.menu_buttons:
            if button.handle_event(event):
                if button.label == "Start Game":
                    self.start_new_game()
                elif button is self.mode_button:
                    self._toggle_mode()
                elif button.label == "Rules":
                    self.state = STATE_RULES
                elif button.label == "Quit":
                    self.running = False

    def _handle_rules_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.state = STATE_MENU
            return

        if self.rules_back_button and self.rules_back_button.handle_event(event):
            self.state = STATE_MENU

    def _handle_playing_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.state = STATE_MENU
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._is_ai_turn():
                return
            self._try_play_card(event.pos)

    def _handle_winner_event(self, event: pygame.event.Event) -> None:
        for button in self.winner_buttons:
            if button.handle_event(event):
                if button.label == "Play Again":
                    self.start_new_game()
                elif button.label == "Main Menu":
                    self.state = STATE_MENU
                elif button.label == "Quit":
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

    def _draw_title(self, title: str, y: int) -> None:
        shadow = self.title_font.render(title, True, BLACK)
        shadow_rect = shadow.get_rect(center=(SCREEN_WIDTH // 2 + 3, y + 3))
        self.screen.blit(shadow, shadow_rect)

        title_surface = self.title_font.render(title, True, LIGHT_GOLD)
        title_rect = title_surface.get_rect(center=(SCREEN_WIDTH // 2, y))
        self.screen.blit(title_surface, title_rect)

    def _draw_menu(self) -> None:
        panel = pygame.Rect(0, 0, 670, 610)
        panel.center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
        draw_panel(self.screen, panel, alpha=130)

        self._draw_title("Kartouna", y=170)

        subtitle = self.subtitle_font.render("Moroccan Card Heritage", True, CREAM)
        subtitle_rect = subtitle.get_rect(center=(SCREEN_WIDTH // 2, 226))
        self.screen.blit(subtitle, subtitle_rect)

        line = pygame.Rect(0, 0, 360, 2)
        line.center = (SCREEN_WIDTH // 2, 252)
        pygame.draw.rect(self.screen, GOLD, line)

        mode_text = self.text_font.render(
            f"Selected Mode: {'1 vs AI' if self.selected_mode == '1vsAI' else '1 vs 1'}",
            True,
            LIGHT_GOLD,
        )
        mode_rect = mode_text.get_rect(center=(SCREEN_WIDTH // 2, 279))
        self.screen.blit(mode_text, mode_rect)

        for button in self.menu_buttons:
            button.draw(self.screen, self.button_font)

    def _draw_rules(self) -> None:
        panel = pygame.Rect(0, 0, 980, 620)
        panel.center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
        draw_panel(self.screen, panel, alpha=165)

        self._draw_title("Rules", y=110)

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

        start_y = 168
        for index, line in enumerate(rules):
            text = self.text_font.render(line, True, WHITE)
            text_rect = text.get_rect(midleft=(165, start_y + index * 42))
            self.screen.blit(text, text_rect)

        if self.rules_back_button:
            self.rules_back_button.draw(self.screen, self.button_font)

    def _draw_score_panels(self) -> None:
        top_panel = pygame.Rect(20, 15, 355, 92)
        bottom_panel = pygame.Rect(20, SCREEN_HEIGHT - 107, 355, 92)
        turn_panel = pygame.Rect(0, 0, 530, 72)
        turn_panel.center = (SCREEN_WIDTH // 2, 38)

        draw_panel(self.screen, top_panel, alpha=150)
        draw_panel(self.screen, bottom_panel, alpha=150)
        draw_panel(self.screen, turn_panel, alpha=160)

        p1 = self.players[0]
        p2 = self.players[1]

        p2_line = self.small_font.render(
            f"P2 Score: {p2.score} | Hand: {len(p2.hand)} | Captured: {len(p2.captured_cards)}",
            True,
            CREAM,
        )
        p1_line = self.small_font.render(
            f"P1 Score: {p1.score} | Hand: {len(p1.hand)} | Captured: {len(p1.captured_cards)}",
            True,
            CREAM,
        )

        self.screen.blit(p2_line, (33, 41 - p2_line.get_height() // 2))
        self.screen.blit(p1_line, (33, SCREEN_HEIGHT - 73 - p1_line.get_height() // 2))

        current = self.players[self.current_player_index]
        if self.turn_locked:
            turn_label = "Resolving move..."
        else:
            turn_label = f"Current Turn: {current.name}"

        turn_text = self.text_font.render(turn_label, True, LIGHT_GOLD)
        turn_rect = turn_text.get_rect(center=(turn_panel.centerx, turn_panel.centery - 12))
        self.screen.blit(turn_text, turn_rect)

        deck_remaining = self.deck.remaining() if self.deck else 0
        round_text = self.small_font.render(
            f"Round: {self.round_number} | Deck: {deck_remaining}",
            True,
            CREAM,
        )
        round_rect = round_text.get_rect(center=(turn_panel.centerx, turn_panel.centery + 14))
        self.screen.blit(round_text, round_rect)

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
        table_panel = pygame.Rect(130, 175, SCREEN_WIDTH - 260, SCREEN_HEIGHT - 350)
        draw_zellige_table(self.screen, table_panel, self.assets, self.time_since_start)

        self._draw_score_panels()
        self._draw_deck_placeholder()
        self._draw_cards()

        if self.info_message:
            info_surface = self.small_font.render(self.info_message, True, LIGHT_GOLD)
            info_rect = info_surface.get_rect(center=(SCREEN_WIDTH // 2, 88))
            self.screen.blit(info_surface, info_rect)

        if self._is_ai_turn():
            hint_text = f"AI ({self.ai_difficulty.title()}) is thinking..."
        else:
            hint_text = "Click one card from the active player hand"

        hint = self.small_font.render(hint_text, True, WHITE)
        hint_rect = hint.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 16))
        self.screen.blit(hint, hint_rect)

    def _draw_winner(self) -> None:
        panel = pygame.Rect(0, 0, 650, 620)
        panel.center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
        draw_panel(self.screen, panel, alpha=160)

        center = (SCREEN_WIDTH // 2, 190)
        rings = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        for i in range(6):
            radius = 80 + (i * 23) + int(math.sin(self.victory_time * 2.8 + i) * 6)
            alpha = max(18, 70 - i * 8)
            pygame.draw.circle(rings, (226, 179, 74, alpha), center, radius, width=2)
        self.screen.blit(rings, (0, 0))

        pulse_size = int(62 + (math.sin(self.victory_time * 5.5) * 4))
        winner_font = self.assets.get_font(pulse_size, bold=True)

        winner_text = winner_font.render(self.winner_message, True, LIGHT_GOLD)
        winner_rect = winner_text.get_rect(center=(SCREEN_WIDTH // 2, 190))
        self.screen.blit(winner_text, winner_rect)

        score_line = self.subtitle_font.render(
            f"Final Score - P1: {self.players[0].score} | P2: {self.players[1].score}",
            True,
            CREAM,
        )
        score_rect = score_line.get_rect(center=(SCREEN_WIDTH // 2, 300))
        self.screen.blit(score_line, score_rect)

        for button in self.winner_buttons:
            button.draw(self.screen, self.button_font)

    def render(self) -> None:
        if self.state == STATE_MENU:
            draw_menu_background(self.screen, self.assets, self.time_since_start)
            self._draw_menu()
        else:
            draw_moroccan_background(self.screen, self.assets, self.time_since_start)

        if self.state == STATE_RULES:
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
