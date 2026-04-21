from __future__ import annotations

import pygame

from settings import BLACK, CARD_HEIGHT, CARD_WIDTH, CREAM, DARK_RED, GOLD


class Card:
    """Represents one game card with visual data and interaction helpers."""

    def __init__(
        self,
        value: int,
        suit: str,
        image: pygame.Surface | None,
        back_image: pygame.Surface | None,
        position: tuple[float, float] = (0, 0),
        owner: str | None = None,
    ) -> None:
        self.value = value
        self.suit = suit
        self.image = image
        self.back_image = back_image
        self.position = pygame.Vector2(position)
        self.owner = owner
        self.face_up = True

        self.rect = pygame.Rect(
            int(self.position.x), int(self.position.y), CARD_WIDTH, CARD_HEIGHT
        )

    def set_owner(self, owner: str | None) -> None:
        self.owner = owner

    def set_position(self, position: tuple[float, float] | pygame.Vector2) -> None:
        self.position.update(position)
        self.rect.topleft = (int(self.position.x), int(self.position.y))

    def move_by(self, delta: tuple[float, float] | pygame.Vector2) -> None:
        self.set_position((self.position.x + delta[0], self.position.y + delta[1]))

    def is_clicked(self, mouse_pos: tuple[int, int]) -> bool:
        return self.rect.collidepoint(mouse_pos)

    def draw(
        self,
        surface: pygame.Surface,
        font: pygame.font.Font,
        hidden: bool = False,
        outlined: bool = False,
    ) -> None:
        chosen = self.back_image if hidden else self.image

        if chosen is not None:
            surface.blit(chosen, self.rect.topleft)
        else:
            self._draw_fallback(surface, font, hidden)

        if outlined:
            pygame.draw.rect(surface, GOLD, self.rect.inflate(6, 6), width=3, border_radius=8)

    def _draw_fallback(
        self, surface: pygame.Surface, font: pygame.font.Font, hidden: bool
    ) -> None:
        base_color = DARK_RED if hidden else CREAM
        text_color = CREAM if hidden else BLACK

        pygame.draw.rect(surface, base_color, self.rect, border_radius=10)
        pygame.draw.rect(surface, GOLD, self.rect, width=3, border_radius=10)

        if not hidden:
            label = f"{self.value} {self.suit[:1]}"
            value_surface = font.render(label, True, text_color)
            text_rect = value_surface.get_rect(center=self.rect.center)
            surface.blit(value_surface, text_rect)
