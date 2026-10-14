"""PyInstaller entry point for the owned desktop backend."""

from app.desktop_server import main


if __name__ == "__main__":
    raise SystemExit(main())
