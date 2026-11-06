# Loads settings from environment variables and the .env file. We keep all
# provider and database config here so switching models or databases later
# is just an env change, not a code change.

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # database
    database_url: str = "postgresql+psycopg://tutor:tutor@localhost:5432/tutor"

    # chat model provider. points at OpenAI for now. later we point these
    # at the ASU Bedrock key, ideally with no code change.
    llm_provider: str = "openai"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-6-luna"

    # embeddings run on a local model so retrieval does not depend on which
    # chat provider we use.
    embed_model: str = "BAAI/bge-small-en-v1.5"

    # where uploaded files are saved on disk
    upload_dir: str = "uploads"


settings = Settings()
