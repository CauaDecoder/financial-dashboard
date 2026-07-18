from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ColorTokens:
    # Ouro
    ouro_50: str = "#F6EBD2"
    ouro_200: str = "#E4C583"
    ouro_500: str = "#C9973A"
    ouro_700: str = "#8B6420"
    ouro_900: str = "#4A3510"

    # Verde
    verde_50: str = "#DFF0E3"
    verde_200: str = "#8FCBA0"
    verde_600: str = "#1F5C3A"
    verde_800: str = "#174D30"
    verde_950: str = "#0A2317"

    # Neutros
    neutro_50: str = "#F7F6F3"
    neutro_100: str = "#EDEBE6"
    neutro_300: str = "#C9C6BE"
    neutro_500: str = "#8B8880"
    neutro_900: str = "#1A1917"

    # Semânticas
    sucesso_bg: str = "#EAF3DE"
    sucesso_texto: str = "#27500A"
    sucesso_dot: str = "#3B6D1A"

    erro_bg: str = "#FCEBEB"
    erro_texto: str = "#791F1F"
    erro_dot: str = "#A32D2D"

    atencao_bg: str = "#FAEEDA"
    atencao_texto: str = "#633806"
    atencao_dot: str = "#854F04"

    info_bg: str = "#E6F1FB"
    info_texto: str = "#0C447C"
    info_dot: str = "#185FAC"

    sidebar_bg: str = "#1C1C1A"

    @property
    def background(self) -> str: return self.neutro_50

    @property
    def surface(self) -> str: return "#FFFFFF"

    @property
    def surface_tint(self) -> str: return self.neutro_100

    @property
    def surface_alt(self) -> str: return self.neutro_50

    @property
    def border(self) -> str: return self.neutro_300

    @property
    def border_soft(self) -> str: return self.neutro_100

    @property
    def border_strong(self) -> str: return self.neutro_500

    @property
    def text(self) -> str: return self.neutro_900

    @property
    def text_muted(self) -> str: return self.neutro_500

    @property
    def text_soft(self) -> str: return self.neutro_300

    @property
    def sidebar(self) -> str: return self.sidebar_bg

    @property
    def sidebar_group(self) -> str: return self.neutro_500

    @property
    def gold(self) -> str: return self.ouro_500

    @property
    def gold_soft(self) -> str: return self.ouro_50



@dataclass(frozen=True)
class SpacingTokens:
    px2: int = 2
    px4: int = 4
    px8: int = 8
    px12: int = 12
    px16: int = 16
    px24: int = 24
    px32: int = 32


@dataclass(frozen=True)
class RadiusTokens:
    sidebar_item: int = 6
    control: int = 10
    card: int = 14
    container: int = 18
    pill: int = 999


@dataclass(frozen=True)
class TypographyTokens:
    page_title_px: int = 24
    section_title_px: int = 18
    button_px: int = 14
    body_px: int = 13
    caption_px: int = 11
    mono_value_px: int = 22
    sidebar_group_px: int = 9


@dataclass(frozen=True)
class ShadowTokens:
    soft: str = "0 8px 24px rgba(28, 28, 26, 0.06)"
    subtle: str = "0 2px 10px rgba(28, 28, 26, 0.04)"


COLORS = ColorTokens()
SPACING = SpacingTokens()
RADIUS = RadiusTokens()
TYPOGRAPHY = TypographyTokens()
SHADOWS = ShadowTokens()


SIDEBAR_SECTIONS: tuple[tuple[str, tuple[tuple[str, int], ...]], ...] = (
    (
        "PRINCIPAL",
        (
            ("Dashboard", 0),
            ("Dashboard avancado", 1),
            ("Planejamento", 2),
        ),
    ),
    (
        "FINANCEIRO",
        (
            ("Contas", 3),
            ("Lancamentos", 4),
            ("Pagar e receber", 5),
        ),
    ),
    (
        "OPERACOES",
        (
            ("Importacoes", 6),
            ("Asaas", 7),
            ("PDV e estoque", 9),
            ("Compras", 10),
            ("Documentos", 11),
        ),
    ),
    (
        "SISTEMA",
        (
            ("Aprovacoes sensiveis", 8),
            ("Usuarios", 12),
            ("Auditoria", 13),
            ("Backups", 14),
            ("Configuracoes", 15),
        ),
    ),
)


def app_stylesheet() -> str:
    return f"""
    QWidget {{
        background: {COLORS.background};
        color: {COLORS.text};
        font-family: "Segoe UI Variable Display", "Segoe UI", "Geist Sans";
        font-size: {TYPOGRAPHY.body_px}px;
    }}
    QWidget#AppShell {{
        background: {COLORS.background};
    }}
    QWidget#LoginShell {{
        background: {COLORS.background};
    }}
    QFrame#LoginHero {{
        border-image: url("assets/bg_login.png") 0 0 0 0 stretch stretch;
        border-radius: 28px;
    }}
    QFrame#LoginPanel {{
        background: rgba(255, 255, 255, 0.985);
        border: 1px solid rgba(232, 217, 191, 0.92);
        border-radius: 28px;
        box-shadow: 0 22px 60px rgba(8, 17, 34, 0.18);
    }}
    QFrame#LoginBadge {{
        background: rgba(255, 255, 255, 0.12);
        border: 1px solid rgba(255, 255, 255, 0.18);
        border-radius: 999px;
    }}
    QLabel#LoginBrand {{
        color: {COLORS.surface};
        font-size: 18px;
        font-weight: 600;
        background: transparent;
    }}
    QLabel#LoginHeroTitle {{
        color: {COLORS.surface};
        font-size: 38px;
        font-weight: 700;
        letter-spacing: -0.4px;
        background: transparent;
    }}
    QLabel#LoginHeroSubtitle {{
        color: rgba(255, 255, 255, 0.72);
        font-size: {TYPOGRAPHY.body_px}px;
        background: transparent;
    }}
    QWidget#PageSurface {{
        background: transparent;
    }}
    QScrollArea {{
        border: 0;
        background: transparent;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 6px 0 6px 0;
    }}
    QScrollBar::handle:vertical {{
        background: {COLORS.border_strong};
        border-radius: 5px;
        min-height: 28px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: transparent;
        border: 0;
    }}
    QLabel#LoginTitle {{
        font-size: 30px;
        font-weight: 700;
        letter-spacing: -0.3px;
        padding: 0;
        background: transparent;
    }}
    QLabel#PageTitle {{
        font-size: {TYPOGRAPHY.page_title_px}px;
        font-weight: 600;
        letter-spacing: 0.3px;
    }}
    QLabel#SectionTitle {{
        font-size: {TYPOGRAPHY.section_title_px}px;
        font-weight: 500;
    }}
    QLabel#SectionCaption {{
        color: {COLORS.text_muted};
        font-size: {TYPOGRAPHY.body_px}px;
    }}
    QLabel#FieldLabel {{
        font-size: {TYPOGRAPHY.body_px}px;
        font-weight: 500;
        color: {COLORS.text};
        background: transparent;
    }}
    QLabel#SidebarBrand {{
        background: transparent;
        color: {COLORS.surface};
        font-size: 15px;
        font-weight: 600;
    }}
    QLabel#SidebarGroup {{
        background: transparent;
        color: {COLORS.sidebar_group};
        font-size: {TYPOGRAPHY.sidebar_group_px}px;
        font-weight: 600;
        letter-spacing: 1.2px;
        text-transform: uppercase;
    }}
    QLabel#MutedText {{
        color: {COLORS.text_muted};
        background: transparent;
    }}
    QLabel#EmptyStateIcon {{
        color: {COLORS.text_soft};
        font-size: 28px;
        background: transparent;
    }}
    QFrame#Sidebar {{
        background: {COLORS.sidebar};
    }}
    QFrame#PageCard, QFrame#KpiCard, QFrame#EmptyState, QDialog {{
        background: {COLORS.surface};
        border: 1px solid {COLORS.border};
        border-radius: {RADIUS.container}px;
    }}
    QFrame#LoginCard {{
        background: {COLORS.surface};
        border: 1px solid {COLORS.border};
        border-radius: {RADIUS.container}px;
    }}
    QFrame#PageCardAlt {{
        background: {COLORS.surface_tint};
        border: 1px solid {COLORS.border_soft};
        border-radius: {RADIUS.container}px;
    }}
    QFrame#KpiCard {{
        border-radius: {RADIUS.card}px;
    }}
    QFrame#FilterRail {{
        background: {COLORS.surface_alt};
        border: 1px solid {COLORS.border};
        border-radius: {RADIUS.container}px;
    }}
    QLineEdit, QComboBox, QDateEdit, QPlainTextEdit, QSpinBox {{
        background: {COLORS.surface};
        border: 1px solid {COLORS.border_soft};
        border-radius: {RADIUS.control}px;
        padding: 10px 12px;
        min-height: 24px;
        selection-background-color: {COLORS.gold};
    }}
    QLineEdit:hover, QComboBox:hover, QDateEdit:hover, QPlainTextEdit:hover, QSpinBox:hover {{
        border: 1px solid {COLORS.border_strong};
        background: {COLORS.surface_tint};
    }}
    QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QPlainTextEdit:focus, QSpinBox:focus {{
        border: 1px solid {COLORS.gold};
        background: {COLORS.surface};
    }}
    QLineEdit:disabled, QComboBox:disabled, QDateEdit:disabled,
    QPlainTextEdit:disabled, QSpinBox:disabled {{
        color: {COLORS.text_soft};
        background: {COLORS.surface_alt};
    }}
    QComboBox::drop-down, QDateEdit::drop-down {{
        border: 0;
        width: 28px;
        background: transparent;
    }}
    QComboBox::down-arrow, QDateEdit::down-arrow {{
        width: 0px;
        height: 0px;
    }}
    QComboBox QAbstractItemView {{
        background: {COLORS.surface};
        color: {COLORS.text};
        border: 1px solid {COLORS.border};
        border-radius: {RADIUS.control}px;
        outline: 0;
        padding: 6px;
        selection-background-color: {COLORS.gold_soft};
        selection-color: {COLORS.text};
    }}
    QComboBox QAbstractItemView::item {{
        min-height: 30px;
        padding: 6px 10px;
        border-radius: {RADIUS.control - 2}px;
        margin: 2px 4px;
    }}
    QComboBox QAbstractItemView::item:hover {{
        background: {COLORS.surface_tint};
        color: {COLORS.text};
    }}
    QComboBox QAbstractItemView::item:selected {{
        background: {COLORS.gold_soft};
        color: {COLORS.text};
    }}
    QPushButton {{
        border-radius: {RADIUS.control}px;
        padding: 10px 14px;
        font-size: {TYPOGRAPHY.button_px}px;
        font-weight: 500;
        border: 1px solid {COLORS.border};
        background: {COLORS.surface};
        color: {COLORS.text};
    }}
    QPushButton:hover {{
        border-color: {COLORS.border_strong};
        background: {COLORS.surface_tint};
    }}
    QPushButton:focus {{
        border-color: {COLORS.gold};
    }}
    QPushButton:disabled {{
        color: {COLORS.text_soft};
        background: {COLORS.surface_alt};
        border-color: {COLORS.border};
    }}
    QTableWidget {{
        background: {COLORS.surface};
        border: 1px solid {COLORS.border_soft};
        border-radius: {RADIUS.container}px;
        gridline-color: {COLORS.border_soft};
        selection-background-color: {COLORS.gold_soft};
        selection-color: {COLORS.text};
    }}
    QHeaderView::section {{
        background: {COLORS.surface};
        color: {COLORS.text_muted};
        font-size: {TYPOGRAPHY.caption_px}px;
        font-weight: 600;
        text-transform: uppercase;
        border: 0;
        border-bottom: 1px solid {COLORS.border_soft};
        padding: 12px;
    }}
    QTableCornerButton::section {{
        background: {COLORS.surface};
        border: 0;
        border-bottom: 1px solid {COLORS.border_soft};
    }}
    QCheckBox {{
        spacing: 8px;
        background: transparent;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border-radius: 4px;
        border: 1px solid {COLORS.border_strong};
        background: {COLORS.surface};
    }}
    QCheckBox::indicator:checked {{
        background: {COLORS.gold};
        border-color: {COLORS.gold};
    }}
    """
