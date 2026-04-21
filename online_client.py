from __future__ import annotations

import argparse
import json
import queue
import socket
import threading

import pygame

from card import Card
from settings import (
    CARD_GAP,
    CARD_HEIGHT,
    CARD_WIDTH,
    FPS,
    GOLD,
    HAND_SIZE,
    LIGHT_GOLD,
    MAX_TABLE_CARDS_PER_ROW,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    TABLE_GAP,
    TITLE,
    WHITE,
)
from ui import AssetManager, draw_moroccan_background, draw_panel, draw_zellige_table


class JsonConnection:
    def __init__(self, host: str, port: int) -> None:
        self.socket = socket.create_connection((host, port), timeout=10)
        self.socket.settimeout(None)
        self.out_lock = threading.Lock()
        self.messages: queue.Queue[dict] = queue.Queue()
        self.running = True

        self.reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.reader_thread.start()

    def _reader_loop(self) -> None:
        reader = self.socket.makefile("r", encoding="utf-8")

        try:
            for line in reader:
                line = line.strip()
                if not line:
                    continue

                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue

                self.messages.put(payload)
        except OSError:
            pass
        finally:
            self.running = False
            self.messages.put({
                "type": "disconnect",
                "message": "Disconnected from server.",
            })
            try:
                reader.close()
            except OSError:
                pass

    def send(self, payload: dict) -> None:
        if not self.running:
            return

        data = (json.dumps(payload) + "\n").encode("utf-8")
        with self.out_lock:
            try:
                self.socket.sendall(data)
            except OSError:
                self.running = False

    def poll_messages(self) -> list[dict]:
        polled: list[dict] = []
        while True:
            try:
                polled.append(self.messages.get_nowait())
            except queue.Empty:
                break
        return polled

    def close(self) -> None:
        self.running = False
        try:
            self.socket.close()
        except OSError:
            pass


class OnlineClientGame:
    """Pygame online client for hidden-hand 1v1 Kartouna."""

    def __init__(self, server_host: str, server_port: int) -> None:
        pygame.init()

        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption(f"{TITLE} - Online 1v1")
        self.clock = pygame.time.Clock()
        self.running = True

        self.assets = AssetManager(mixer_available=False)
        self.title_font = self.assets.get_font(54, bold=True)
        self.text_font = self.assets.get_font(24)
        self.small_font = self.assets.get_font(20)
        self.card_font = self.assets.get_font(18, bold=True)

        self.time_since_start = 0.0
        self.player_id: int | None = None
        self.connection_status = "Connecting..."
        self.info_message = ""
        self.current_state: dict | None = None
        self.pending_action = False
        self.clickable_cards: list[tuple[Card, int]] = []

        try:
            self.connection = JsonConnection(server_host, server_port)
            self.connection_status = f"Connected to {server_host}:{server_port}"
        except OSError:
            self.connection = None
            self.connection_status = "Unable to connect to server"

    def _hand_targets(self, count: int, player_index: int) -> list[tuple[int, int]]:
        if count <= 0:
            return []

        total_width = (count * CARD_WIDTH) + ((count - 1) * CARD_GAP)
        start_x = (SCREEN_WIDTH - total_width) // 2
        y = SCREEN_HEIGHT - CARD_HEIGHT - 30 if player_index == 0 else 30

        return [(start_x + i * (CARD_WIDTH + CARD_GAP), y) for i in range(count)]

    def _table_targets(self, count: int) -> list[tuple[int, int]]:
        if count <= 0:
            return []

        rows = (count + MAX_TABLE_CARDS_PER_ROW - 1) // MAX_TABLE_CARDS_PER_ROW
        total_height = (rows * CARD_HEIGHT) + ((rows - 1) * 14)
        start_y = (SCREEN_HEIGHT // 2) - (total_height // 2)

        targets: list[tuple[int, int]] = []
        for index in range(count):
            row = index // MAX_TABLE_CARDS_PER_ROW
            col = index % MAX_TABLE_CARDS_PER_ROW

            cards_in_row = min(MAX_TABLE_CARDS_PER_ROW, count - (row * MAX_TABLE_CARDS_PER_ROW))
            row_width = (cards_in_row * CARD_WIDTH) + ((cards_in_row - 1) * TABLE_GAP)
            row_start_x = (SCREEN_WIDTH - row_width) // 2

            x = row_start_x + col * (CARD_WIDTH + TABLE_GAP)
            y = start_y + row * (CARD_HEIGHT + 14)
            targets.append((x, y))

        return targets

    def _is_my_turn(self) -> bool:
        if self.current_state is None:
            return False
        return bool(self.current_state.get("is_your_turn", False))

    def _handle_network_messages(self) -> None:
        if self.connection is None:
            return

        for payload in self.connection.poll_messages():
            message_type = payload.get("type")

            if message_type == "welcome":
                self.player_id = int(payload.get("player_id", 0))
                self.info_message = payload.get("message", "")
            elif message_type == "state":
                self.current_state = payload
                self.pending_action = False
                self.info_message = payload.get("event", "")
            elif message_type == "info":
                self.info_message = payload.get("message", "")
            elif message_type == "error":
                self.info_message = payload.get("message", "")
                self.pending_action = False
            elif message_type == "disconnect":
                self.info_message = payload.get("message", "Disconnected")
                self.connection_status = "Disconnected"
                self.connection = None

    def _play_hand_index(self, hand_index: int) -> None:
        if self.connection is None:
            return
        if self.pending_action:
            return

        self.connection.send({"type": "play_card", "hand_index": hand_index})
        self.pending_action = True

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return

            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.running = False
                return

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if not self._is_my_turn():
                    continue
                if self.pending_action:
                    continue
                if self.current_state is None:
                    continue
                if self.current_state.get("game_over"):
                    continue

                for card, hand_index in reversed(self.clickable_cards):
                    if card.is_clicked(event.pos):
                        self._play_hand_index(hand_index)
                        break

    def update(self, dt: float) -> None:
        self.time_since_start += dt
        self._handle_network_messages()

    def _draw_connection_wait(self) -> None:
        panel = pygame.Rect(0, 0, 740, 280)
        panel.center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
        draw_panel(self.screen, panel, alpha=170)

        title = self.title_font.render("Kartouna Online", True, LIGHT_GOLD)
        title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, panel.top + 80))
        self.screen.blit(title, title_rect)

        status = self.text_font.render(self.connection_status, True, WHITE)
        status_rect = status.get_rect(center=(SCREEN_WIDTH // 2, panel.top + 150))
        self.screen.blit(status, status_rect)

        info = self.small_font.render(self.info_message or "Waiting...", True, WHITE)
        info_rect = info.get_rect(center=(SCREEN_WIDTH // 2, panel.top + 200))
        self.screen.blit(info, info_rect)

    def _draw_hud(self) -> None:
        if self.current_state is None:
            return

        top_panel = pygame.Rect(20, 15, 370, 92)
        bottom_panel = pygame.Rect(20, SCREEN_HEIGHT - 107, 370, 92)
        turn_panel = pygame.Rect(0, 0, 550, 74)
        turn_panel.center = (SCREEN_WIDTH // 2, 38)

        draw_panel(self.screen, top_panel, alpha=150)
        draw_panel(self.screen, bottom_panel, alpha=150)
        draw_panel(self.screen, turn_panel, alpha=160)

        your_score = int(self.current_state.get("your_score", 0))
        opp_score = int(self.current_state.get("opponent_score", 0))
        your_hand_count = len(self.current_state.get("your_hand", []))
        opp_hand_count = int(self.current_state.get("opponent_hand_count", 0))

        p2_line = self.small_font.render(
            f"Opponent Score: {opp_score} | Hand: {opp_hand_count}",
            True,
            WHITE,
        )
        p1_line = self.small_font.render(
            f"Your Score: {your_score} | Hand: {your_hand_count}",
            True,
            WHITE,
        )

        self.screen.blit(p2_line, (33, 41 - p2_line.get_height() // 2))
        self.screen.blit(p1_line, (33, SCREEN_HEIGHT - 73 - p1_line.get_height() // 2))

        if self.current_state.get("game_over"):
            turn_label = "Game finished"
        elif self._is_my_turn():
            turn_label = "Your turn"
        else:
            turn_label = "Opponent turn"

        turn_text = self.text_font.render(turn_label, True, LIGHT_GOLD)
        turn_rect = turn_text.get_rect(center=(turn_panel.centerx, turn_panel.centery - 12))
        self.screen.blit(turn_text, turn_rect)

        round_number = int(self.current_state.get("round_number", 1))
        deck_remaining = int(self.current_state.get("deck_remaining", 0))
        round_text = self.small_font.render(
            f"Round: {round_number} | Deck: {deck_remaining}",
            True,
            WHITE,
        )
        round_rect = round_text.get_rect(center=(turn_panel.centerx, turn_panel.centery + 15))
        self.screen.blit(round_text, round_rect)

    def _draw_cards(self) -> None:
        if self.current_state is None:
            return

        self.clickable_cards = []
        table_cards = self.current_state.get("table_cards", [])
        your_hand = self.current_state.get("your_hand", [])
        opponent_count = int(self.current_state.get("opponent_hand_count", 0))

        opp_targets = self._hand_targets(opponent_count, player_index=1)
        hand_targets = self._hand_targets(len(your_hand), player_index=0)
        table_targets = self._table_targets(len(table_cards))

        back = self.assets.get_card_back(CARD_WIDTH, CARD_HEIGHT)

        for target in opp_targets:
            hidden_card = Card(
                value=0,
                suit="",
                image=None,
                back_image=back,
                position=target,
                owner="Opponent",
            )
            hidden_card.draw(self.screen, self.card_font, hidden=True, outlined=False)

        for idx, card_data in enumerate(table_cards):
            face = self.assets.get_card_face(
                int(card_data["value"]),
                str(card_data["suit"]),
                CARD_WIDTH,
                CARD_HEIGHT,
            )
            table_card = Card(
                value=int(card_data["value"]),
                suit=str(card_data["suit"]),
                image=face,
                back_image=back,
                position=table_targets[idx],
                owner="Table",
            )
            table_card.draw(self.screen, self.card_font, hidden=False, outlined=False)

        for idx, card_data in enumerate(your_hand):
            face = self.assets.get_card_face(
                int(card_data["value"]),
                str(card_data["suit"]),
                CARD_WIDTH,
                CARD_HEIGHT,
            )
            your_card = Card(
                value=int(card_data["value"]),
                suit=str(card_data["suit"]),
                image=face,
                back_image=back,
                position=hand_targets[idx],
                owner="You",
            )

            outlined = self._is_my_turn() and not self.pending_action
            your_card.draw(self.screen, self.card_font, hidden=False, outlined=outlined)
            self.clickable_cards.append((your_card, idx))

    def _draw_event_text(self) -> None:
        if self.current_state is None:
            return

        event_text = self.current_state.get("event") or self.info_message
        if event_text:
            event_surface = self.small_font.render(str(event_text), True, LIGHT_GOLD)
            event_rect = event_surface.get_rect(center=(SCREEN_WIDTH // 2, 88))
            self.screen.blit(event_surface, event_rect)

        if self.current_state.get("game_over"):
            winner = str(self.current_state.get("winner", "Draw"))
            panel = pygame.Rect(0, 0, 620, 230)
            panel.center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
            draw_panel(self.screen, panel, alpha=180)

            if self.player_id is None:
                win_label = f"Winner: {winner}"
            elif winner == "Draw":
                win_label = "Draw"
            elif winner == f"Player {self.player_id + 1}":
                win_label = "You Win"
            else:
                win_label = "You Lose"

            text1 = self.title_font.render(win_label, True, LIGHT_GOLD)
            text1_rect = text1.get_rect(center=(SCREEN_WIDTH // 2, panel.top + 80))
            self.screen.blit(text1, text1_rect)

            p1 = int(self.current_state.get("score_p1", 0))
            p2 = int(self.current_state.get("score_p2", 0))
            score_line = self.text_font.render(f"Final Score - P1: {p1} | P2: {p2}", True, WHITE)
            score_rect = score_line.get_rect(center=(SCREEN_WIDTH // 2, panel.top + 145))
            self.screen.blit(score_line, score_rect)

            exit_line = self.small_font.render("Press ESC to quit", True, WHITE)
            exit_rect = exit_line.get_rect(center=(SCREEN_WIDTH // 2, panel.top + 190))
            self.screen.blit(exit_line, exit_rect)

    def render(self) -> None:
        draw_moroccan_background(self.screen, self.assets, self.time_since_start)

        if self.current_state is None:
            self._draw_connection_wait()
        else:
            table_panel = pygame.Rect(130, 175, SCREEN_WIDTH - 260, SCREEN_HEIGHT - 350)
            draw_zellige_table(self.screen, table_panel, self.assets, self.time_since_start)
            self._draw_hud()
            self._draw_cards()
            self._draw_event_text()

            if self.current_state.get("game_over"):
                hint = "Game finished"
            elif self._is_my_turn() and not self.pending_action:
                hint = "Your turn: click one card"
            elif self._is_my_turn() and self.pending_action:
                hint = "Move sent... waiting for server"
            else:
                hint = "Opponent turn"

            hint_surface = self.small_font.render(hint, True, WHITE)
            hint_rect = hint_surface.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 16))
            self.screen.blit(hint_surface, hint_rect)

        pygame.display.flip()

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            self._handle_events()
            self.update(dt)
            self.render()

        if self.connection is not None:
            self.connection.close()
        pygame.quit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Kartouna online client")
    parser.add_argument("--host", default="127.0.0.1", help="Server IP")
    parser.add_argument("--port", type=int, default=5050, help="Server TCP port")
    args = parser.parse_args()

    game = OnlineClientGame(server_host=args.host, server_port=args.port)
    game.run()


if __name__ == "__main__":
    main()
