import os
from enum import Enum
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class ApiService(Enum):
    DOUBAO = "DOUBAO_API_KEY"
    QWEN = "QWEN_API_KEY"
    GPT = "GPT_API_KEY"
    GEMINI = "GEMINI_API_KEY"


def get_api_key(service: ApiService):
    """
    Get API key for the given service from environment variables.
    Usage: get_api_key(ApiService.DOUBAO)
    """
    return os.getenv(service.value)
