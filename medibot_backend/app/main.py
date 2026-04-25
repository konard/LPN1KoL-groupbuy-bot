from .bot import build_application
from .config import settings


def main() -> None:
    """Run the Telegram polling process."""

    application = build_application(settings)
    application.run_polling()


if __name__ == "__main__":
    main()
