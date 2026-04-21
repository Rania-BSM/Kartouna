from __future__ import annotations

import argparse
import json
import random
import socket
import threading
from collections import Counter
from dataclasses import dataclass, field

HAND_SIZE = 5
STARTING_TABLE_CARDS = 4
SUITS = ("Dhab", "Sif", "Kasa", "3ssa")
VALUES = (1, 2, 3, 4, 5, 6, 7, 10, 11, 12)


@dataclass
class ServerPlayer:
    name: str
    hand: list[dict] = field(default_factory=list)
    score: int = 0
    captured_count: int = 0


class RondaOnlineState:
    """Authoritative online game state. Clients only receive private-safe views."""

    def __init__(self) -> None:
        self.players = [ServerPlayer("Player 1"), ServerPlayer("Player 2")]
        self.deck: list[dict] = []
        self.table_cards: list[dict] = []
        self.current_turn = 0
        self.round_number = 0
        self.last_capturer_index: int | None = None
        self.game_over = False
        self.winner_label = "Draw"
        self.last_event = "Waiting for players..."

    def reset_game(self) -> None:
        self.players = [ServerPlayer("Player 1"), ServerPlayer("Player 2")]
        self.deck = self._build_deck()
        random.shuffle(self.deck)
        self.table_cards = []
        self.current_turn = 0
        self.round_number = 0
        self.last_capturer_index = None
        self.game_over = False
        self.winner_label = "Draw"
        self.last_event = "Game started"
        self._deal_round(include_table_cards=True, cards_per_player=HAND_SIZE)

    def _build_deck(self) -> list[dict]:
        deck: list[dict] = []
        for suit in SUITS:
            for value in VALUES:
                deck.append({"value": value, "suit": suit})
        return deck

    def _draw(self, count: int) -> list[dict]:
        draw_count = min(max(0, count), len(self.deck))
        drawn = self.deck[-draw_count:]
        if draw_count > 0:
            del self.deck[-draw_count:]
        return drawn

    def _cards_to_deal_each_player(self) -> int:
        if len(self.deck) >= HAND_SIZE * 2:
            return HAND_SIZE
        return len(self.deck) // 2

    def _apply_hand_combo_bonus(self, player_index: int) -> list[str]:
        player = self.players[player_index]
        counts = Counter(card["value"] for card in player.hand)

        labels: list[str] = []
        total_bonus = 0
        for value, count in sorted(counts.items()):
            if count >= 4:
                total_bonus += 10
                labels.append(f"4-of-kind ({value}) +10")
            elif count == 3:
                total_bonus += 5
                labels.append(f"Tringa ({value}) +5")
            elif count == 2:
                total_bonus += 1
                labels.append(f"Ronda ({value}) +1")

        if total_bonus > 0:
            player.score += total_bonus

        return labels

    def _deal_round(
        self,
        include_table_cards: bool,
        cards_per_player: int | None = None,
    ) -> bool:
        if cards_per_player is None:
            cards_per_player = self._cards_to_deal_each_player()

        if cards_per_player <= 0:
            return False

        self.round_number += 1
        for player in self.players:
            player.hand.extend(self._draw(cards_per_player))

        if include_table_cards:
            self.table_cards.extend(self._draw(min(STARTING_TABLE_CARDS, len(self.deck))))

        bonuses: list[str] = []
        for idx, player in enumerate(self.players):
            labels = self._apply_hand_combo_bonus(idx)
            for label in labels:
                bonuses.append(f"{player.name}: {label}")

        event = f"Round {self.round_number}: dealt {cards_per_player} card(s) each"
        if bonuses:
            event += " | " + " | ".join(bonuses)
        self.last_event = event
        return True

    def _collect_remaining_table_cards(self) -> None:
        if not self.table_cards:
            return
        if self.last_capturer_index is None:
            return

        collector = self.players[self.last_capturer_index]
        remaining = len(self.table_cards)
        collector.score += remaining
        collector.captured_count += remaining
        self.table_cards.clear()
        self.last_event = (
            f"{collector.name} collected remaining {remaining} table cards"
        )

    def _finish_game(self) -> None:
        self._collect_remaining_table_cards()

        p1_score = self.players[0].score
        p2_score = self.players[1].score
        if p1_score > p2_score:
            self.winner_label = "Player 1"
        elif p2_score > p1_score:
            self.winner_label = "Player 2"
        else:
            self.winner_label = "Draw"

        self.game_over = True
        self.last_event = (
            f"Game Over - Winner: {self.winner_label}"
            f" | Score P1={self.players[0].score} P2={self.players[1].score}"
        )

    def play_card(self, player_index: int, hand_index: int) -> tuple[bool, str]:
        if self.game_over:
            return False, "Game already finished."
        if player_index != self.current_turn:
            return False, "Not your turn."

        player = self.players[player_index]
        if hand_index < 0 or hand_index >= len(player.hand):
            return False, "Invalid hand index."

        played_card = player.hand.pop(hand_index)
        matching = [card for card in self.table_cards if card["value"] == played_card["value"]]

        if matching:
            self.table_cards = [
                card for card in self.table_cards if card["value"] != played_card["value"]
            ]

            captured_count = 1 + len(matching)
            player.captured_count += captured_count
            player.score += captured_count
            self.last_capturer_index = player_index

            self.last_event = f"{player.name} captured {captured_count} cards"
            if len(self.table_cards) == 0:
                player.score += 1
                self.last_event += " + Missa +1"
        else:
            self.table_cards.append(played_card)
            self.last_event = (
                f"{player.name} played {played_card['value']} {played_card['suit']}"
            )

        if not self.players[0].hand and not self.players[1].hand:
            cards_per_player = self._cards_to_deal_each_player()
            if cards_per_player > 0:
                self.current_turn = 1 - self.current_turn
                self._deal_round(include_table_cards=False, cards_per_player=cards_per_player)
            else:
                self._finish_game()
            return True, self.last_event

        self.current_turn = 1 - self.current_turn
        return True, self.last_event

    def player_view(self, player_index: int) -> dict:
        opponent_index = 1 - player_index

        return {
            "type": "state",
            "player_id": player_index,
            "your_hand": [dict(card) for card in self.players[player_index].hand],
            "opponent_hand_count": len(self.players[opponent_index].hand),
            "table_cards": [dict(card) for card in self.table_cards],
            "your_score": self.players[player_index].score,
            "opponent_score": self.players[opponent_index].score,
            "score_p1": self.players[0].score,
            "score_p2": self.players[1].score,
            "current_turn": self.current_turn,
            "is_your_turn": self.current_turn == player_index and not self.game_over,
            "round_number": self.round_number,
            "deck_remaining": len(self.deck),
            "event": self.last_event,
            "game_over": self.game_over,
            "winner": self.winner_label,
        }


class OnlineRondaServer:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.state = RondaOnlineState()
        self.clients: list[socket.socket | None] = [None, None]
        self.running = True
        self.lock = threading.Lock()
        self.server_socket: socket.socket | None = None

    def _send_json(self, conn: socket.socket, payload: dict) -> None:
        message = (json.dumps(payload) + "\n").encode("utf-8")
        conn.sendall(message)

    def _safe_send(self, player_index: int, payload: dict) -> None:
        conn = self.clients[player_index]
        if conn is None:
            return
        try:
            self._send_json(conn, payload)
        except OSError:
            pass

    def _broadcast_states(self) -> None:
        with self.lock:
            payloads = [
                (idx, self.state.player_view(idx))
                for idx, conn in enumerate(self.clients)
                if conn is not None
            ]

        for idx, payload in payloads:
            self._safe_send(idx, payload)

    def _broadcast_info(self, message: str) -> None:
        for idx, conn in enumerate(self.clients):
            if conn is not None:
                self._safe_send(idx, {"type": "info", "message": message})

    def _shutdown_server(self) -> None:
        self.running = False

        for idx, conn in enumerate(self.clients):
            if conn is None:
                continue
            try:
                conn.close()
            except OSError:
                pass
            self.clients[idx] = None

        if self.server_socket is not None:
            try:
                self.server_socket.close()
            except OSError:
                pass

    def _handle_disconnect(self, player_index: int) -> None:
        with self.lock:
            if self.clients[player_index] is not None:
                try:
                    self.clients[player_index].close()
                except OSError:
                    pass
                self.clients[player_index] = None

            other_index = 1 - player_index
            other_conn_exists = self.clients[other_index] is not None

        if other_conn_exists:
            self._safe_send(other_index, {
                "type": "info",
                "message": "Other player disconnected. Server is closing.",
            })

        self._shutdown_server()

    def _handle_message(self, player_index: int, payload: dict) -> None:
        message_type = payload.get("type")
        if message_type != "play_card":
            self._safe_send(player_index, {
                "type": "error",
                "message": "Unknown message type.",
            })
            return

        try:
            hand_index = int(payload.get("hand_index", -1))
        except (TypeError, ValueError):
            hand_index = -1

        with self.lock:
            success, message = self.state.play_card(player_index, hand_index)

        if not success:
            self._safe_send(player_index, {"type": "error", "message": message})
            return

        self._broadcast_states()

    def _client_loop(self, player_index: int, conn: socket.socket) -> None:
        file_reader = conn.makefile("r", encoding="utf-8")

        try:
            for line in file_reader:
                line = line.strip()
                if not line:
                    continue

                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    self._safe_send(player_index, {
                        "type": "error",
                        "message": "Invalid JSON payload.",
                    })
                    continue

                self._handle_message(player_index, payload)
        except OSError:
            pass
        finally:
            try:
                file_reader.close()
            except OSError:
                pass
            self._handle_disconnect(player_index)

    def serve_forever(self) -> None:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((self.host, self.port))
        listener.listen(2)
        self.server_socket = listener

        print(f"[Server] Listening on {self.host}:{self.port}")
        print("[Server] Waiting for two players...")

        try:
            while self.running:
                try:
                    conn, addr = listener.accept()
                except OSError:
                    break

                with self.lock:
                    free_slot = next(
                        (idx for idx, client in enumerate(self.clients) if client is None),
                        None,
                    )
                    if free_slot is not None:
                        self.clients[free_slot] = conn

                if free_slot is None:
                    try:
                        self._send_json(conn, {
                            "type": "info",
                            "message": "Server full. Try again later.",
                        })
                    finally:
                        conn.close()
                    continue

                print(f"[Server] Player {free_slot + 1} connected from {addr}")
                self._safe_send(free_slot, {
                    "type": "welcome",
                    "player_id": free_slot,
                    "message": f"Connected as Player {free_slot + 1}",
                })

                thread = threading.Thread(
                    target=self._client_loop,
                    args=(free_slot, conn),
                    daemon=True,
                )
                thread.start()

                with self.lock:
                    both_connected = self.clients[0] is not None and self.clients[1] is not None
                    if both_connected:
                        self.state.reset_game()

                if both_connected:
                    self._broadcast_info("Both players connected. Game started.")
                    self._broadcast_states()
                else:
                    self._safe_send(free_slot, {
                        "type": "info",
                        "message": "Waiting for second player...",
                    })
        finally:
            self._shutdown_server()
            print("[Server] Closed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Kartouna online server")
    parser.add_argument("--host", default="0.0.0.0", help="Host IP to bind")
    parser.add_argument("--port", type=int, default=5050, help="TCP port")
    args = parser.parse_args()

    server = OnlineRondaServer(host=args.host, port=args.port)
    server.serve_forever()


if __name__ == "__main__":
    main()
