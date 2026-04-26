"""
Configurações centralizadas do projeto
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # === API MERCADO LIVRE ===
    CLIENT_ID = os.getenv("MERCADOLIVRE_CLIENT_ID")
    CLIENT_SECRET = os.getenv("MERCADOLIVRE_CLIENT_SECRET")
    API_BASE_URL = "https://api.mercadolibre.com"

    # === SELENIUM ===
    USER_AGENT = os.getenv(
        "USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    # Site do ML
    ML_URL = "https://www.mercadolivre.com.br"

    # === OUTPUT ===
    OUTPUT_FORMAT = os.getenv("OUTPUT_FORMAT", "console")  # console, json, csv

    # === TIMEOUTS ===
    API_TIMEOUT = 10
    SELENIUM_TIMEOUT = 15

    # === VALIDAÇÃO ===
    @classmethod
    def validate(cls):
        if not cls.CLIENT_ID or not cls.CLIENT_SECRET:
            print("⚠️  Aviso: Credenciais da API não configuradas.")
            print("   Crie um arquivo .env com MERCADOLIVRE_CLIENT_ID e MERCADOLIVRE_CLIENT_SECRET")
            print("   Obtenha em: https://developers.mercadolibre.com.br/")
            return False
        return True
