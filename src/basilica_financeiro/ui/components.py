from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from basilica_financeiro.ui.design_system import COLORS, RADIUS, SPACING, TYPOGRAPHY


@dataclass(frozen=True)
class BadgePalette:
    fg: str
    bg: str


BADGE_PALETTES: dict[str, BadgePalette] = {
    "paid": BadgePalette(COLORS.green, COLORS.green_soft),
    "overdue": BadgePalette(COLORS.red, COLORS.red_soft),
    "due-soon": BadgePalette(COLORS.amber, COLORS.amber_soft),
    "open": BadgePalette(COLORS.blue, COLORS.blue_soft),
    "cancelled": BadgePalette(COLORS.neutral_badge, COLORS.neutral_badge_soft),
    "income": BadgePalette(COLORS.green, COLORS.green_soft),
    "expense": BadgePalette(COLORS.red, COLORS.red_soft),
    "transfer": BadgePalette(COLORS.blue, COLORS.blue_soft),
    "pending": BadgePalette(COLORS.amber, COLORS.amber_soft),
}


BUTTON_STYLES: dict[str, str] = {
    "primary": (
        f"QPushButton {{ background: {COLORS.green}; color: {COLORS.surface}; "
        f"border: 1px solid {COLORS.green}; }}"
        f"QPushButton:hover {{ background: #267149; border-color: #267149; }}"
    ),
    "secondary": (
        f"QPushButton {{ background: {COLORS.surface}; color: {COLORS.text}; "
        f"border: 1px solid {COLORS.border_strong}; }}"
        f"QPushButton:hover {{ border-color: {COLORS.gold}; color: {COLORS.text}; }}"
    ),
    "ghost": (
        f"QPushButton {{ background: transparent; color: {COLORS.text}; "
        f"border: 1px solid transparent; }}"
        f"QPushButton:hover {{ background: {COLORS.surface_alt}; border-color: {COLORS.border}; }}"
    ),
    "danger": (
        f"QPushButton {{ background: {COLORS.surface}; color: {COLORS.danger}; "
        f"border: 1px solid #E7B7B2; }}"
        f"QPushButton:hover {{ background: {COLORS.red_soft}; border-color: {COLORS.red}; }}"
    ),
    "icon-only": (
        f"QPushButton {{ min-width: 32px; max-width: 32px; min-height: 32px; "
        f"padding: 0; border-radius: {RADIUS.control}px; }}"
    ),
    "pill": (
        f"QPushButton {{ background: {COLORS.surface_alt}; color: {COLORS.text_muted}; "
        f"border: 1px solid transparent; border-radius: {RADIUS.pill}px; padding: 8px 16px; }}"
        f"QPushButton:hover {{ border-color: {COLORS.border}; color: {COLORS.text}; }}"
    ),
    "pill-active": (
        f"QPushButton {{ background: {COLORS.surface}; color: {COLORS.text}; "
        f"border: 1px solid {COLORS.border}; border-radius: {RADIUS.pill}px; padding: 8px 16px; }}"
    ),
    "sidebar": (
        f"QPushButton {{ background: transparent; color: {COLORS.sidebar_text}; "
        f"border: 1px solid transparent; border-radius: {RADIUS.sidebar_item}px; "
        f"padding: 10px 12px; text-align: left; }}"
        f"QPushButton:hover {{ background: {COLORS.sidebar_hover}; color: {COLORS.sidebar_text}; }}"
    ),
    "sidebar-active": (
        f"QPushButton {{ background: {COLORS.sidebar_active_bg}; color: {COLORS.gold}; "
        f"border: 1px solid transparent; border-radius: {RADIUS.sidebar_item}px; "
        f"padding: 10px 12px; text-align: left; font-weight: 500; }}"
    ),
}


def make_button(
    label: str,
    *,
    variant: str = "secondary",
    icon_text: str | None = None,
) -> QPushButton:
    button = QPushButton(f"{icon_text}  {label}".strip() if icon_text else label)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setMinimumHeight(42)
    button.setStyleSheet(BUTTON_STYLES.get(variant, BUTTON_STYLES["secondary"]))
    return button


def make_filter_button(label: str, *, active: bool = False) -> QPushButton:
    variant = "pill-active" if active else "pill"
    button = make_button(label, variant=variant)
    button.setCheckable(True)
    button.setChecked(active)
    return button


def make_sidebar_button(label: str, *, active: bool = False) -> QPushButton:
    button = make_button(label, variant="sidebar-active" if active else "sidebar")
    button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    button.setMinimumHeight(40)
    return button


class BadgeLabel(QLabel):
    def __init__(self, text: str, tone: str, *, show_dot: bool = True) -> None:
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_badge(text, tone=tone, show_dot=show_dot)

    def set_badge(self, text: str, *, tone: str, show_dot: bool = True) -> None:
        palette = BADGE_PALETTES.get(tone, BADGE_PALETTES["cancelled"])
        prefix = "* " if show_dot else ""
        self.setText(f"{prefix}{text}")
        self.setStyleSheet(
            "QLabel {"
            f"color: {palette.fg};"
            f"background: {palette.bg};"
            f"border-radius: {RADIUS.pill}px;"
            "padding: 5px 10px;"
            f"font-size: {TYPOGRAPHY.caption_px}px;"
            "font-weight: 600;"
            "}"
        )


class KpiCard(QFrame):
    def __init__(
        self,
        *,
        title: str,
        value: str,
        subtitle: str,
        icon_text: str,
        tone: str = "neutral",
    ) -> None:
        super().__init__()
        self.setObjectName("KpiCard")
        self.setMinimumHeight(148)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING.px16, SPACING.px16, SPACING.px16, SPACING.px16)
        layout.setSpacing(SPACING.px12)

        tone_color = {
            "positive": COLORS.green,
            "negative": COLORS.red,
            "warning": COLORS.amber,
            "info": COLORS.blue,
            "neutral": COLORS.text,
        }.get(tone, COLORS.text)

        header = QHBoxLayout()
        icon = QLabel(icon_text)
        icon.setStyleSheet(
            f"QLabel {{ color: {tone_color}; font-size: 16px; background: transparent; }}"
        )
        title_label = QLabel(title)
        title_label.setObjectName("MutedText")
        title_label.setStyleSheet(
            "QLabel {"
            f"color: {COLORS.text_muted};"
            f"font-size: {TYPOGRAPHY.button_px}px;"
            "font-weight: 500;"
            "background: transparent;"
            "}"
        )
        header.addWidget(icon)
        header.addWidget(title_label)
        header.addStretch(1)

        value_label = QLabel(value)
        value_label.setStyleSheet(
            f"QLabel {{ color: {tone_color}; font-family: Consolas, 'Cascadia Mono'; "
            f"font-size: {TYPOGRAPHY.mono_value_px}px; "
            "font-weight: 500; background: transparent; }"
        )
        subtitle_label = QLabel(subtitle)
        subtitle_label.setStyleSheet(
            f"QLabel {{ color: {tone_color if tone != 'neutral' else COLORS.text_muted}; "
            f"font-size: {TYPOGRAPHY.button_px}px; font-weight: 500; background: transparent; }}"
        )

        layout.addLayout(header)
        layout.addWidget(value_label)
        layout.addWidget(subtitle_label)


class EmptyState(QFrame):
    def __init__(
        self,
        *,
        icon_text: str,
        title: str,
        description: str,
        cta: QPushButton | None = None,
    ) -> None:
        super().__init__()
        self.setObjectName("EmptyState")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon = QLabel(icon_text)
        icon.setObjectName("EmptyStateIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        headline = QLabel(title)
        headline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        headline.setStyleSheet(
            "QLabel {"
            f"font-size: {TYPOGRAPHY.section_title_px}px;"
            "font-weight: 500;"
            "background: transparent;"
            "}"
        )
        body = QLabel(description)
        body.setObjectName("MutedText")
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.setWordWrap(True)

        layout.addWidget(icon)
        layout.addWidget(headline)
        layout.addWidget(body)
        if cta is not None:
            layout.addWidget(cta, alignment=Qt.AlignmentFlag.AlignCenter)


class FinancialTable(QTableWidget):
    def __init__(self, headers: list[str]) -> None:
        super().__init__(0, len(headers))
        self.setHorizontalHeaderLabels(headers)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(False)
        self.verticalHeader().setVisible(False)
        self.setShowGrid(False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setWordWrap(False)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.horizontalHeader().setStretchLastSection(False)
        self.horizontalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.setStyleSheet(
            self.styleSheet()
            + (
                "QTableWidget::item { padding: 12px; border-bottom: 1px solid "
                f"{COLORS.border}; }}"
                "QTableWidget::item:selected { background: transparent; }"
            )
        )

    def set_empty_message(self, title: str, description: str | None = None) -> None:
        self.setRowCount(1)
        self.clearContents()
        self.setSpan(0, 0, 1, self.columnCount())
        text = title if description is None else f"{title}\n{description}"
        item = QTableWidgetItem(text)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        item.setForeground(QColor(COLORS.text_muted))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(0, 0, item)
        self.setRowHeight(0, 92)


def make_checkbox() -> QWidget:
    wrapper = QWidget()
    layout = QHBoxLayout(wrapper)
    layout.setContentsMargins(12, 0, 0, 0)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    checkbox = QCheckBox()
    checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
    layout.addWidget(checkbox)
    return wrapper


def build_section_card() -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setObjectName("PageCard")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(SPACING.px24, SPACING.px24, SPACING.px24, SPACING.px24)
    layout.setSpacing(SPACING.px16)
    return card, layout


def build_muted_section_card() -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setObjectName("PageCardAlt")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(SPACING.px24, SPACING.px24, SPACING.px24, SPACING.px24)
    layout.setSpacing(SPACING.px16)
    return card, layout


def build_section_header(title: str, caption: str | None = None) -> QWidget:
    wrapper = QWidget()
    layout = QVBoxLayout(wrapper)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    heading = QLabel(title)
    heading.setObjectName("SectionTitle")
    layout.addWidget(heading)
    if caption is not None:
        sub = QLabel(caption)
        sub.setObjectName("SectionCaption")
        sub.setWordWrap(True)
        layout.addWidget(sub)
    return wrapper


def build_table_card(
    *,
    title: str,
    caption: str | None = None,
    table: QTableWidget,
    empty_state: QWidget | None = None,
) -> QFrame:
    card, layout = build_section_card()
    layout.addWidget(build_section_header(title, caption))
    if empty_state is not None:
        layout.addWidget(empty_state)
    else:
        layout.addWidget(table)
    return card


def style_data_table(
    table: QTableWidget,
    *,
    min_height: int = 240,
    stretch_last: bool = True,
) -> None:
    table.setMinimumHeight(min_height)
    table.horizontalHeader().setMinimumSectionSize(88)
    table.horizontalHeader().setStretchLastSection(stretch_last)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    if stretch_last and table.columnCount() > 0:
        table.horizontalHeader().setSectionResizeMode(
            table.columnCount() - 1,
            QHeaderView.ResizeMode.Stretch,
        )


def build_responsive_button_row() -> tuple[QWidget, QGridLayout]:
    wrapper = QWidget()
    layout = QGridLayout(wrapper)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setHorizontalSpacing(SPACING.px12)
    layout.setVerticalSpacing(SPACING.px12)
    return wrapper, layout


def build_table_scroll_area(widget: QWidget) -> QScrollArea:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setWidget(widget)
    return scroll


def add_table_cell(
    table: QTableWidget,
    row: int,
    column: int,
    value: str,
    *,
    align_right: bool = False,
) -> None:
    item = QTableWidgetItem(value)
    if align_right:
        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    table.setItem(row, column, item)


def make_two_column_form() -> tuple[QFrame, QGridLayout]:
    frame = QFrame()
    frame.setObjectName("PageCard")
    layout = QGridLayout(frame)
    layout.setContentsMargins(SPACING.px24, SPACING.px24, SPACING.px24, SPACING.px24)
    layout.setHorizontalSpacing(SPACING.px16)
    layout.setVerticalSpacing(SPACING.px16)
    return frame, layout
