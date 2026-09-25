#!/usr/bin/env python3
"""Startpunkt der nativen Hotdesk-Desktopanwendung."""


def main() -> None:
    from app.desktop_app import main as app_main
    app_main()


if __name__ == "__main__":
    main()
