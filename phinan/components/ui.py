"""Shared UI components for the warmer and more dynamic visual design."""

import reflex as rx

def data_section(title: str, children, **kwargs) -> rx.Component:
    """Borderless data section with subtle background."""
    return rx.box(
        rx.text(
            title,
            size="1",
            color="var(--pfs-text-muted)",
            margin_bottom="8px",
            text_transform="uppercase",
            letter_spacing="0.05em",
        ),
        children,
        padding="20px",
        background="var(--pfs-surface)",
        border_radius="8px",
        color="var(--pfs-text)",  # Enforce text color on custom surface
        **kwargs
    )


def card_header(title: str, *right, icon=None, left=None) -> rx.Component:
    """Standard card header followed by a divider.

    Layout: [icon] title [left-adjacent content] ... spacer ... [right content]
    """
    left_items = []
    if icon is not None:
        left_items.append(rx.icon(icon, size=18))
    left_items.append(rx.heading(title, size="4"))
    if left is not None:
        left_items.append(left)
    return rx.fragment(
        rx.hstack(
            rx.hstack(*left_items, spacing="2", align="center"),
            rx.spacer(),
            *right,
            width="100%",
            align="center",
        ),
        rx.divider(),
    )


def content_card(*children, **kwargs) -> rx.Component:
    """Standard card with soft border and breathable padding."""
    return rx.box(
        *children,
        padding="24px",
        background="var(--pfs-surface)",
        border="1px solid var(--gray-a4)",
        border_radius="12px",
        color="var(--pfs-text)",  # Enforce text color on custom surface
        **kwargs
    )


def synthesis_card(*children, **kwargs) -> rx.Component:
    """Special premium treatment for AI synthesis and core insights."""
    return rx.box(
        *children,
        padding="28px",
        background="var(--pfs-synthesis-bg)",
        border="1px solid var(--pfs-synthesis-border)",
        border_radius="16px",
        box_shadow="0 2px 8px rgba(0,0,0,0.04)",
        color="var(--pfs-text)",  # Enforce text color on custom surface
        **kwargs
    )
