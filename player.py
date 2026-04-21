from __future__ import annotations

from collections import Counter

from card import Card


class Player:
    """Holds player state: hand, captured cards, score and identity."""

    def __init__(self, name: str, seat: str) -> None:
        self.name = name
        self.seat = seat
        self.hand: list[Card] = []
        self.captured_cards: list[Card] = []
        self.score = 0

    def reset_for_new_game(self) -> None:
        self.hand.clear()
        self.captured_cards.clear()
        self.score = 0

    def receive_cards(self, cards: list[Card]) -> None:
        for card in cards:
            card.set_owner(self.name)
            self.hand.append(card)

    def play_card(self, card_index: int) -> Card | None:
        if 0 <= card_index < len(self.hand):
            return self.hand.pop(card_index)
        return None

    def capture(self, cards: list[Card]) -> None:
        for card in cards:
            card.set_owner(self.name)
        self.captured_cards.extend(cards)
        self.score += len(cards)

    def add_bonus(self, points: int) -> None:
        self.score += max(0, points)

    def apply_hand_combo_bonus(self) -> tuple[int, list[str]]:
        """Apply Ronda/Tringa/four-of-a-kind bonuses for the current hand."""
        value_counter = Counter(card.value for card in self.hand)

        total_bonus = 0
        labels: list[str] = []

        for value, count in sorted(value_counter.items()):
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
            self.add_bonus(total_bonus)

        return total_bonus, labels

    def has_cards(self) -> bool:
        return len(self.hand) > 0
