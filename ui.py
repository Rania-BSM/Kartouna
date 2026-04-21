from __future__ import annotations

import math

import pygame

from settings import (
    BLACK,
    BLENDER_EXPORTS_DIR,
    CREAM,
    DARK_RED,
    DEEP_RED,
    FONTS_DIR,
    GOLD,
    IMAGES_DIR,
    LIGHT_GOLD,
    SOUNDS_DIR,
)


def _lerp_color(
    start: tuple[int, int, int] | tuple[int, int, int, int],
    end: tuple[int, int, int] | tuple[int, int, int, int],
    ratio: float,
) -> tuple[int, ...]:
    clamped = max(0.0, min(1.0, ratio))
    return tuple(
        int(start[i] + ((end[i] - start[i]) * clamped)) for i in range(len(start))
    )


def _draw_zellige_star(
    surface: pygame.Surface,
    center: tuple[int, int],
    outer_radius: int,
    inner_radius: int,
    fill_color: tuple[int, int, int],
    line_color: tuple[int, int, int],
) -> None:
    cx, cy = center
    points: list[tuple[float, float]] = []
    step = (math.pi * 2.0) / 16.0

    for index in range(16):
        angle = (-math.pi / 2.0) + (index * step)
        radius = outer_radius if index % 2 == 0 else inner_radius
        points.append((cx + math.cos(angle) * radius, cy + math.sin(angle) * radius))

    pygame.draw.polygon(surface, fill_color, points)
    pygame.draw.polygon(surface, line_color, points, width=2)


class AssetManager:
    """Loads and caches fonts, generated card art, images and sounds."""

    def __init__(self, mixer_available: bool = True) -> None:
        self.mixer_available = mixer_available
        self.font_cache: dict[tuple[int, bool], pygame.font.Font] = {}
        self.image_cache: dict[str, pygame.Surface] = {}
        self.card_cache: dict[tuple, pygame.Surface] = {}
        self.sound_cache: dict[str, pygame.mixer.Sound] = {}
        self.background_cache: dict[tuple, pygame.Surface] = {}

    def get_font(self, size: int, bold: bool = False) -> pygame.font.Font:
        key = (size, bold)
        if key in self.font_cache:
            return self.font_cache[key]

        preferred_fonts = [
            "Amiri-Regular.ttf",
            "NotoNaskhArabic-Regular.ttf",
            "EBGaramond-Regular.ttf",
        ]

        loaded_font: pygame.font.Font | None = None
        for filename in preferred_fonts:
            font_path = FONTS_DIR / filename
            if font_path.exists():
                loaded_font = pygame.font.Font(str(font_path), size)
                break

        if loaded_font is None:
            loaded_font = pygame.font.SysFont("georgia", size, bold=bold)

        self.font_cache[key] = loaded_font
        return loaded_font

    def load_image(self, file_name: str) -> pygame.Surface | None:
        if file_name in self.image_cache:
            return self.image_cache[file_name]

        search_paths = [IMAGES_DIR / file_name, BLENDER_EXPORTS_DIR / file_name]
        for image_path in search_paths:
            if image_path.exists():
                image = pygame.image.load(str(image_path)).convert_alpha()
                self.image_cache[file_name] = image
                return image

        return None

    def get_card_face(self, value: int, suit: str, width: int, height: int) -> pygame.Surface:
        key = ("face", value, suit, width, height)
        if key in self.card_cache:
            return self.card_cache[key]

        surface = pygame.Surface((width, height), pygame.SRCALPHA)

        pygame.draw.rect(surface, CREAM, (0, 0, width, height), border_radius=10)
        pygame.draw.rect(surface, GOLD, (0, 0, width, height), width=4, border_radius=10)

        inner = pygame.Rect(8, 8, width - 16, height - 16)
        pygame.draw.rect(surface, (235, 223, 193), inner, border_radius=8)

        suit_color = {
            "Dhab": (170, 128, 35),
            "Sif": (66, 72, 94),
            "Kasa": (152, 56, 45),
            "3ssa": (77, 116, 78),
            # Backward-compatible aliases.
            "Coins": (170, 128, 35),
            "Cups": (152, 56, 45),
            "Swords": (66, 72, 94),
            "Batons": (77, 116, 78),
        }.get(suit, BLACK)

        deco_points = [
            (width // 2, 18),
            (width - 18, height // 2),
            (width // 2, height - 18),
            (18, height // 2),
        ]
        pygame.draw.polygon(surface, suit_color, deco_points, width=2)

        value_font = self.get_font(30, bold=True)
        suit_font = self.get_font(20)

        value_text = value_font.render(str(value), True, BLACK)
        suit_text = suit_font.render(suit, True, suit_color)

        surface.blit(value_text, (12, 8))
        surface.blit(
            pygame.transform.rotate(value_text, 180),
            (width - value_text.get_width() - 12, height - value_text.get_height() - 8),
        )

        suit_rect = suit_text.get_rect(center=(width // 2, height // 2))
        surface.blit(suit_text, suit_rect)

        self.card_cache[key] = surface
        return surface

    def get_card_back(self, width: int, height: int) -> pygame.Surface:
        key = ("back", width, height)
        if key in self.card_cache:
            return self.card_cache[key]

        surface = pygame.Surface((width, height), pygame.SRCALPHA)

        pygame.draw.rect(surface, DEEP_RED, (0, 0, width, height), border_radius=10)
        pygame.draw.rect(surface, GOLD, (0, 0, width, height), width=4, border_radius=10)

        margin = 10
        inner = pygame.Rect(margin, margin, width - (margin * 2), height - (margin * 2))
        pygame.draw.rect(surface, DARK_RED, inner, border_radius=8)
        pygame.draw.rect(surface, LIGHT_GOLD, inner, width=2, border_radius=8)

        step = 16
        for x in range(inner.left + 6, inner.right, step):
            for y in range(inner.top + 6, inner.bottom, step):
                diamond = [(x, y - 4), (x + 4, y), (x, y + 4), (x - 4, y)]
                pygame.draw.polygon(surface, (210, 161, 61), diamond, width=1)

        label_font = self.get_font(22, bold=True)
        label = label_font.render("K", True, LIGHT_GOLD)
        label_rect = label.get_rect(center=(width // 2, height // 2))
        surface.blit(label, label_rect)

        self.card_cache[key] = surface
        return surface

    def get_background(self, size: tuple[int, int]) -> pygame.Surface:
        key = ("game_background", size)
        if key in self.background_cache:
            return self.background_cache[key]

        width, height = size
        surface = pygame.Surface(size)

        top = (30, 8, 11)
        bottom = (80, 18, 23)
        for y in range(height):
            ratio = y / max(1, height - 1)
            color = _lerp_color(top, bottom, ratio)
            pygame.draw.line(surface, color, (0, y), (width, y))

        pattern = pygame.Surface(size, pygame.SRCALPHA)
        tile = 64
        stroke = (182, 130, 57, 26)

        for x in range(-tile, width + tile, tile):
            for y in range(-tile, height + tile, tile):
                pygame.draw.circle(pattern, stroke, (x, y), 11, width=1)
                pygame.draw.line(pattern, stroke, (x - 11, y), (x + 11, y), width=1)
                pygame.draw.line(pattern, stroke, (x, y - 11), (x, y + 11), width=1)

        surface.blit(pattern, (0, 0))

        vignette = pygame.Surface(size, pygame.SRCALPHA)
        pygame.draw.rect(vignette, (0, 0, 0, 58), (0, 0, width, height), width=0)
        pygame.draw.rect(vignette, (0, 0, 0, 0), (28, 28, width - 56, height - 56), width=0)
        surface.blit(vignette, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)

        self.background_cache[key] = surface
        return surface

    def get_menu_background(self, size: tuple[int, int]) -> pygame.Surface:
        key = ("menu_background", size)
        if key in self.background_cache:
            return self.background_cache[key]

        candidates = (
            "menu_background.png",
            "menu_bg.png",
            "moroccan_menu_bg.png",
            "menu_background.jpg",
            "menu_background.jpeg",
            "menu_background.webp",
        )

        for file_name in candidates:
            image = self.load_image(file_name)
            if image is None:
                continue
            scaled = pygame.transform.smoothscale(image, size)
            self.background_cache[key] = scaled
            return scaled

        fallback = self._build_menu_background_fallback(size)
        self.background_cache[key] = fallback
        return fallback

    def _build_menu_background_fallback(self, size: tuple[int, int]) -> pygame.Surface:
        width, height = size
        surface = pygame.Surface(size)

        top = (42, 5, 9)
        center = (98, 16, 21)
        bottom = (58, 8, 11)

        for y in range(height):
            ratio = y / max(1, height - 1)
            blend = ratio * 2.0 if ratio < 0.5 else (ratio - 0.5) * 2.0
            color = _lerp_color(top, center, blend) if ratio < 0.5 else _lerp_color(center, bottom, blend)
            pygame.draw.line(surface, color, (0, y), (width, y))

        texture = pygame.Surface(size, pygame.SRCALPHA)
        for y in range(0, height + 36, 36):
            for x in range(0, width + 46, 46):
                shift = int((math.sin((x * 0.013) + (y * 0.021)) + 1.0) * 8)
                rect = pygame.Rect(x - 22, y - 16 + shift, 64, 42)
                pygame.draw.arc(texture, (124, 38, 34, 30), rect, 0.2, 3.0, 2)
                pygame.draw.arc(texture, (124, 38, 34, 24), rect.move(10, 8), 3.3, 6.1, 2)

        surface.blit(texture, (0, 0))

        glow = pygame.Surface(size, pygame.SRCALPHA)
        center_x = width // 2
        center_y = height // 2
        max_radius = int(min(width, height) * 0.48)
        for radius in range(max_radius, 30, -8):
            power = radius / max(1, max_radius)
            alpha = int((1.0 - power) * 70)
            if alpha <= 0:
                continue
            color = (188, 53, 40, alpha)
            pygame.draw.circle(glow, color, (center_x, center_y), radius)

        surface.blit(glow, (0, 0))

        # Zellige corner clusters inspired by the provided visual direction.
        self._draw_zellige_cluster(surface, (width - 36, 36), mirror_x=True, mirror_y=False)
        self._draw_zellige_cluster(surface, (36, height - 36), mirror_x=False, mirror_y=True)

        return surface

    def _draw_zellige_cluster(
        self,
        surface: pygame.Surface,
        origin: tuple[int, int],
        mirror_x: bool,
        mirror_y: bool,
    ) -> None:
        ox, oy = origin
        tile = 44
        offsets = (
            (0, 0),
            (1, 0),
            (0, 1),
            (1, 1),
            (2, 1),
            (1, 2),
            (2, 2),
            (3, 2),
            (2, 3),
            (3, 3),
            (4, 3),
            (3, 4),
            (4, 4),
            (5, 4),
        )
        palette = (
            (26, 90, 66),
            (36, 105, 78),
            (121, 51, 22),
            (152, 66, 28),
            (46, 94, 92),
        )

        direction_x = -1 if mirror_x else 1
        direction_y = -1 if mirror_y else 1

        for index, (dx, dy) in enumerate(offsets):
            cx = ox + (dx * tile * direction_x)
            cy = oy + (dy * tile * direction_y)
            fill = palette[index % len(palette)]
            _draw_zellige_star(surface, (cx, cy), 17, 8, fill, (212, 162, 68))
            pygame.draw.circle(surface, (95, 29, 18), (cx, cy), 3)

    def get_table_texture(self, size: tuple[int, int]) -> pygame.Surface:
        key = ("table_texture", size)
        if key in self.background_cache:
            return self.background_cache[key]

        custom_candidates = (
            "table_background.png",
            "table_background.jpg",
            "table_background.jpeg",
            "table_background.webp",
            "zellige_table_background.png",
        )

        for file_name in custom_candidates:
            image = self.load_image(file_name)
            if image is None:
                continue

            table_custom = pygame.transform.smoothscale(image, size)

            overlay = pygame.Surface(size, pygame.SRCALPHA)
            pygame.draw.rect(overlay, (0, 0, 0, 24), (0, 0, size[0], size[1]))
            pygame.draw.rect(overlay, (226, 179, 74, 84), (0, 0, size[0], size[1]), width=3)
            table_custom.blit(overlay, (0, 0))

            self.background_cache[key] = table_custom
            return table_custom

        width, height = size
        table = pygame.Surface(size, pygame.SRCALPHA)

        outer = pygame.Rect(0, 0, width, height)
        pygame.draw.rect(table, (48, 16, 20), outer, border_radius=26)
        pygame.draw.rect(table, (166, 120, 52), outer, width=4, border_radius=26)

        border_rect = outer.inflate(-18, -18)
        pygame.draw.rect(table, (92, 33, 26), border_rect, border_radius=20)
        pygame.draw.rect(table, (211, 164, 74), border_rect, width=2, border_radius=20)

        inner = border_rect.inflate(-34, -34)
        for y in range(inner.height):
            ratio = y / max(1, inner.height - 1)
            color = _lerp_color((16, 58, 45), (25, 94, 69), ratio)
            pygame.draw.line(
                table,
                color,
                (inner.left, inner.top + y),
                (inner.right, inner.top + y),
            )

        grain = pygame.Surface(size, pygame.SRCALPHA)
        for y in range(inner.top, inner.bottom, 8):
            alpha = 10 if ((y // 8) % 2 == 0) else 6
            pygame.draw.line(
                grain,
                (236, 223, 180, alpha),
                (inner.left + 6, y),
                (inner.right - 6, y),
                width=1,
            )
        table.blit(grain, (0, 0))

        self._draw_table_border_tiles(table, border_rect)

        self.background_cache[key] = table
        return table

    def _draw_table_border_tiles(self, surface: pygame.Surface, border_rect: pygame.Rect) -> None:
        palette = (
            (27, 91, 67),
            (38, 107, 78),
            (122, 53, 24),
            (155, 69, 29),
            (52, 95, 93),
        )
        outline = (214, 169, 74)
        step = 42
        radius = 12

        top_y = border_rect.top + 11
        bottom_y = border_rect.bottom - 11
        left_x = border_rect.left + 11
        right_x = border_rect.right - 11

        for index, x in enumerate(range(left_x, right_x + 1, step)):
            fill = palette[index % len(palette)]
            _draw_zellige_star(surface, (x, top_y), radius, 6, fill, outline)
            _draw_zellige_star(surface, (x, bottom_y), radius, 6, fill, outline)

        for index, y in enumerate(range(top_y + step, bottom_y, step)):
            fill = palette[index % len(palette)]
            _draw_zellige_star(surface, (left_x, y), radius, 6, fill, outline)
            _draw_zellige_star(surface, (right_x, y), radius, 6, fill, outline)

    def play_sound(self, file_name: str) -> None:
        if not self.mixer_available:
            return

        if file_name in self.sound_cache:
            self.sound_cache[file_name].play()
            return

        sound_path = SOUNDS_DIR / file_name
        if not sound_path.exists():
            return

        try:
            sound = pygame.mixer.Sound(str(sound_path))
        except pygame.error:
            return

        self.sound_cache[file_name] = sound
        sound.play()

    def play_music(self, file_name: str, loops: int = -1) -> None:
        if not self.mixer_available:
            return

        music_path = SOUNDS_DIR / file_name
        if not music_path.exists():
            return

        try:
            pygame.mixer.music.load(str(music_path))
            pygame.mixer.music.play(loops)
        except pygame.error:
            return


class Button:
    """Simple reusable UI button with hover and click feedback."""

    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        text: str,
        action: str | None = None,
        padding: int = 14,
    ) -> None:
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.label = text
        self.action = action if action is not None else text
        self.padding = max(8, padding)
        self.hovered = False

    def _split_text_lines(
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

    def _truncate_text(
        self,
        text: str,
        font: pygame.font.Font,
        max_width: int,
    ) -> str:
        if font.size(text)[0] <= max_width:
            return text

        suffix = "..."
        trimmed = text
        while trimmed and font.size(trimmed + suffix)[0] > max_width:
            trimmed = trimmed[:-1]

        if not trimmed:
            return suffix
        return trimmed + suffix

    def _fit_text_lines(
        self,
        base_font: pygame.font.Font,
        max_width: int,
        max_height: int,
    ) -> tuple[pygame.font.Font, list[str]]:
        font_candidates: list[pygame.font.Font] = [base_font]
        base_size = max(16, base_font.get_height())
        for size in range(base_size - 1, 13, -1):
            font_candidates.append(pygame.font.SysFont("georgia", size, bold=True))

        for candidate_font in font_candidates:
            lines = self._split_text_lines(self.text, candidate_font, max_width)
            if len(lines) > 3:
                continue

            if any(candidate_font.size(line)[0] > max_width for line in lines):
                continue

            total_height = len(lines) * candidate_font.get_linesize()
            if total_height <= max_height:
                return candidate_font, lines

        fallback = pygame.font.SysFont("georgia", 14, bold=True)
        return fallback, [self._truncate_text(self.text, fallback, max_width)]

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self.rect.collidepoint(event.pos)

        return False

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        self.hovered = self.rect.collidepoint(pygame.mouse.get_pos())

        layer = pygame.Surface(self.rect.size, pygame.SRCALPHA)

        top_color = (136, 34, 40, 245) if not self.hovered else (162, 44, 51, 248)
        bottom_color = (83, 18, 26, 245) if not self.hovered else (105, 28, 35, 248)

        for y in range(self.rect.height):
            ratio = y / max(1, self.rect.height - 1)
            color = _lerp_color(top_color, bottom_color, ratio)
            pygame.draw.line(layer, color, (0, y), (self.rect.width, y))

        if self.hovered:
            shine = pygame.Surface(self.rect.size, pygame.SRCALPHA)
            pygame.draw.ellipse(
                shine,
                (240, 214, 150, 28),
                (8, 2, self.rect.width - 16, self.rect.height // 2),
            )
            layer.blit(shine, (0, 0))

        if self.hovered:
            pygame.draw.rect(layer, (248, 225, 164, 34), layer.get_rect(), border_radius=14)

        surface.blit(layer, self.rect.topleft)
        pygame.draw.rect(surface, GOLD, self.rect, width=3, border_radius=14)
        pygame.draw.rect(surface, (247, 219, 151), self.rect.inflate(-8, -8), width=1, border_radius=12)

        inner_rect = self.rect.inflate(-(self.padding * 2), -(self.padding * 2))
        text_font, lines = self._fit_text_lines(font, inner_rect.width, inner_rect.height)

        line_height = text_font.get_linesize()
        block_height = line_height * len(lines)
        start_y = self.rect.centery - (block_height // 2)

        for index, line in enumerate(lines):
            line_surface = text_font.render(line, True, CREAM)
            line_shadow = text_font.render(line, True, (25, 7, 9))

            line_y = start_y + (index * line_height)
            shadow_rect = line_shadow.get_rect(center=(self.rect.centerx + 1, line_y + (line_height // 2) + 1))
            line_rect = line_surface.get_rect(center=(self.rect.centerx, line_y + (line_height // 2)))

            surface.blit(line_shadow, shadow_rect)
            surface.blit(line_surface, line_rect)


def draw_moroccan_background(
    surface: pygame.Surface,
    assets: AssetManager,
    tick_seconds: float,
) -> None:
    base = assets.get_background(surface.get_size())
    surface.blit(base, (0, 0))

    glow_layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    width, height = surface.get_size()

    for index, x in enumerate((130, width // 2, width - 130)):
        y = int(82 + math.sin((tick_seconds * 1.3) + index) * 9)
        pygame.draw.circle(glow_layer, (238, 193, 87, 24), (x, y), 54)
        pygame.draw.circle(glow_layer, (238, 193, 87, 42), (x, y), 30, width=2)

    surface.blit(glow_layer, (0, 0))


def draw_menu_background(
    surface: pygame.Surface,
    assets: AssetManager,
    tick_seconds: float,
) -> None:
    base = assets.get_menu_background(surface.get_size())
    surface.blit(base, (0, 0))

    width, height = surface.get_size()
    vignette = pygame.Surface(surface.get_size(), pygame.SRCALPHA)

    # Deep-red tint keeps menu screens visually consistent even with custom images.
    tint = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    tint.fill((88, 18, 26, 88))
    surface.blit(tint, (0, 0))

    # Soft cinematic darkening at top/bottom so menu text stays readable.
    for y in range(height):
        top_ratio = 1.0 - min(1.0, y / max(1, height * 0.25))
        bottom_ratio = max(0.0, (y - (height * 0.72)) / max(1, height * 0.28))
        alpha = int((top_ratio * 70) + (bottom_ratio * 90))
        if alpha <= 0:
            continue
        pygame.draw.line(vignette, (0, 0, 0, alpha), (0, y), (width, y))

    pulse = int(20 + (math.sin(tick_seconds * 1.6) * 6))
    pygame.draw.ellipse(
        vignette,
        (227, 176, 71, max(8, pulse)),
        (width // 2 - 260, 110, 520, 180),
        width=2,
    )

    surface.blit(vignette, (0, 0))


def draw_zellige_table(
    surface: pygame.Surface,
    rect: pygame.Rect,
    assets: AssetManager,
    tick_seconds: float,
) -> None:
    table = assets.get_table_texture(rect.size)
    surface.blit(table, rect.topleft)

    shimmer = pygame.Surface(rect.size, pygame.SRCALPHA)
    highlight_alpha = int(14 + (math.sin(tick_seconds * 2.1) * 6))
    pygame.draw.ellipse(
        shimmer,
        (246, 225, 170, max(8, highlight_alpha)),
        (rect.width // 2 - 200, rect.height // 2 - 70, 400, 140),
    )
    pygame.draw.ellipse(
        shimmer,
        (205, 160, 66, 46),
        (rect.width // 2 - 240, rect.height // 2 - 96, 480, 192),
        width=3,
    )

    surface.blit(shimmer, rect.topleft)


def draw_panel(surface: pygame.Surface, rect: pygame.Rect, alpha: int = 150) -> None:
    panel = pygame.Surface(rect.size, pygame.SRCALPHA)

    top_color = (40, 13, 18, alpha)
    bottom_color = (62, 20, 28, alpha)
    for y in range(rect.height):
        ratio = y / max(1, rect.height - 1)
        color = _lerp_color(top_color, bottom_color, ratio)
        pygame.draw.line(panel, color, (0, y), (rect.width, y))

    pattern = pygame.Surface(rect.size, pygame.SRCALPHA)
    for x in range(0, rect.width + 40, 40):
        for y in range(0, rect.height + 40, 40):
            pygame.draw.circle(pattern, (200, 160, 70, 13), (x, y), 6, width=1)
    panel.blit(pattern, (0, 0))

    surface.blit(panel, rect.topleft)
    pygame.draw.rect(surface, GOLD, rect, width=2, border_radius=12)
    pygame.draw.rect(surface, (246, 216, 145), rect.inflate(-8, -8), width=1, border_radius=10)
