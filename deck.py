from __future__ import annotations

import random

from card import Card
from settings import CARD_HEIGHT, CARD_WIDTH


class Deck:
    """Creates and manages a 40-card Moroccan/Spanish-style deck."""

    SUITS = ("Dhab", "Sif", "Kasa", "3ssa")
    VALUES = (1, 2, 3, 4, 5, 6, 7, 10, 11, 12)

    def __init__(self, asset_manager) -> None:
        self.asset_manager = asset_manager
        self.cards: list[Card] = []
        self._build_deck()

    def _build_deck(self) -> None:
        self.cards.clear()
        back_image = self.asset_manager.get_card_back(CARD_WIDTH, CARD_HEIGHT)

        for suit in self.SUITS:
            for value in self.VALUES:
                face_image = self.asset_manager.get_card_face(value, suit, CARD_WIDTH, CARD_HEIGHT)
                self.cards.append(
                    Card(
                        value=value,
                        suit=suit,
                        image=face_image,
                        back_image=back_image,
                    )
                )

    def shuffle(self) -> None:
        random.shuffle(self.cards)

    def draw(self, count: int = 1) -> list[Card]:
        drawn: list[Card] = []
        for _ in range(max(0, min(count, len(self.cards)))):
            drawn.append(self.cards.pop())
        return drawn

    def is_empty(self) -> bool:
        return not self.cards

    def remaining(self) -> int:
        return len(self.cards)
