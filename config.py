from typing import Optional
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


class ProgramEntry(BaseModel):
    priority: int
    progname: str


class Config(BaseSettings):
    program_configs: dict[str, ProgramEntry] = Field(
        default={
            "pdftotext": ProgramEntry(priority=10, progname="pdftotext"),
            "pdf2txt": ProgramEntry(
                priority=20, progname="/app/.venv/bin/pdf2txt.py"
            ),  # this one is not in PATH, set explicitly!
        }
    )

    accepted_buckets: Optional[list[str]] = Field(
        default=None, alias="ACCEPTED_BUCKETS"
    )  # if None, all buckets are allowed!

    @field_validator("accepted_buckets", mode="before")
    @classmethod
    def validate_buckets(cls, v):
        if isinstance(v, str):
            return [item.strip().lower() for item in v.split(",") if item.strip()]
        return v

    cgroup_name: str = "pdftotext"
    host: str = "0.0.0.0"
    port: int = 8888

    default_convert_timeout: int = 180


config = Config()
