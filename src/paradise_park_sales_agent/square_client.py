import os

from dotenv import load_dotenv
from square import Square
from square.environment import SquareEnvironment


load_dotenv()


def build_square_client() -> Square:
    """Create a Square client from protected environment settings."""

    token = os.getenv("SQUARE_ACCESS_TOKEN")
    environment_name = os.getenv(
        "SQUARE_ENVIRONMENT",
        "sandbox",
    ).lower()

    if not token:
        raise RuntimeError(
            "SQUARE_ACCESS_TOKEN is missing. Add it to the local .env file."
        )

    if environment_name == "sandbox":
        environment = SquareEnvironment.SANDBOX
    elif environment_name == "production":
        environment = SquareEnvironment.PRODUCTION
    else:
        raise RuntimeError(
            "SQUARE_ENVIRONMENT must be 'sandbox' or 'production'."
        )

    return Square(
        environment=environment,
        token=token,
    )

