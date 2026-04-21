from __future__ import annotations

import random

from card import Card


def choose_card_easy(hand: list[Card]) -> Card | None:
    """Easy mode: pick any random card."""
    if not hand:
        return None
    return random.choice(hand)


def choose_card_medium(hand: list[Card], table_cards: list[Card]) -> Card | None:
    """Medium mode: prefer random capturing card, else random card."""
    if not hand:
        return None

    capture_cards: list[Card] = []
    for card in hand:
        if any(table_card.value == card.value for table_card in table_cards):
            capture_cards.append(card)

    if capture_cards:
        return random.choice(capture_cards)
    return random.choice(hand)


def choose_card_hard(hand: list[Card], table_cards: list[Card]) -> Card | None:
    """Hard mode: maximize capture count and Missa chance, else play lowest card."""
    if not hand:
        return None

    best_card: Card | None = None
    best_score = -1

    for card in hand:
        matching_cards = [t for t in table_cards if t.value == card.value]
        if not matching_cards:
            continue

        score = len(matching_cards)
        if len(matching_cards) == len(table_cards):
            score += 1  # Missa bonus

        if score > best_score:
            best_score = score
            best_card = card

    if best_card is not None:
        return best_card

    return min(hand, key=lambda card: card.value)


def choose_card_by_difficulty(
    hand: list[Card],
    table_cards: list[Card],
    difficulty: str,
) -> Card | None:
    level = difficulty.lower().strip()

    if level == "easy":
        return choose_card_easy(hand)
    if level == "hard":
        return choose_card_hard(hand, table_cards)
    return choose_card_medium(hand, table_cards)
