import os
import pathlib
import sys

import dotenv
from loguru import logger
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.sources import EnvSettingsSource

# probably not needed as pydantic_settings might do this,
# but ensure .env is loaded early
pyproject_file = dotenv.find_dotenv("pyproject.toml")
dotenv.load_dotenv()

ROOT_DIR = pathlib.Path(pyproject_file).parent


class NotifyingEnvSource(EnvSettingsSource):
    def __call__(self):
        data = super().__call__()
        for key in data:
            if key in os.environ:
                logger.warning(f"{key} overridden by .env variable")
        return data


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )

    LOG_LEVEL: str = "SUCCESS"
    ROOT_DIR: pathlib.Path = ROOT_DIR
    CACHE_DIR: pathlib.Path = ROOT_DIR / "data" / ".cache"

    # @classmethod
    # def settings_customise_sources(
    #     cls,
    #     settings_cls,
    #     init_settings,
    #     env_settings,
    #     dotenv_settings,
    #     file_secret_settings,
    # ):
    #     return (
    #         init_settings,
    #         NotifyingEnvSource(settings_cls),
    #         DotEnvSettingsSource(settings_cls),
    #         file_secret_settings,
    #     )


cfg = Settings()

logger.remove()
logger.add(sys.stdout, level=cfg.LOG_LEVEL)
