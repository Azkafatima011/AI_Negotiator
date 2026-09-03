"""
AI Negotiator — An Autonomous B2B Wholesale Negotiation Platform
Configuration settings for Alibaba Cloud + WhatsApp integration.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Application
    app_name: str = "AI Negotiator"
    debug: bool = True
    version: str = "1.0.0"

    # Database
    database_url: str = "sqlite:///./negotiation.db"

    # Security / JWT
    secret_key: str = "dev-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480

    # Alibaba Cloud Model Studio / Qwen
    alibaba_model_studio_api_key: str = ""
    alibaba_model_studio_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    qwen_model_name: str = "qwen-plus"

    # Alibaba Cloud Services (production)
    alibaba_cloud_access_key_id: str = ""
    alibaba_cloud_access_key_secret: str = ""
    alibaba_cloud_region: str = "ap-south-1"

    # WhatsApp Business Platform
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_webhook_verify_token: str = ""

    # Alibaba.com Open Platform
    alibaba_com_app_key: str = ""
    alibaba_com_app_secret: str = ""

    # Negotiation defaults
    default_max_rounds: int = 10
    default_currency: str = "PKR"

    # Supported currencies
    supported_currencies: list[str] = ["PKR", "USD", "CNY", "EUR", "AED", "SAR"]

    # Supported units
    supported_units: list[str] = [
        "kg", "ton", "metric_ton", "maund", "tola",
        "bale", "piece", "carton", "bag", "container"
    ]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
