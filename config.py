from functools import lru_cache
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
    name: str
    path: str
    template: str


class Config(BaseSettings):
    program_configs: dict[str, ProgramEntry] = Field(
        default={
            "pdftotext": ProgramEntry(
                priority=10,
                name="pdftotext",
                path="pdftotext",
                template="{path} {params} {file_in} {file_out}",
            ),
            "pdf2txt": ProgramEntry(
                priority=20,
                name="pdf2txt",
                path="/app/.venv/bin/pdf2txt.py",
                template="{path} {params} --outfile {file_out} {file_in}",
            ),
        }
    )
    cgroup_prefix: list[str] = ["cgexec", "-g", "memory:pdftotext"]
    accepted_buckets: Optional[list[str]] = None  # if None, all buckets are allowed!

    @field_validator("accepted_buckets", mode="before")
    @classmethod
    def validate_buckets(cls, v):
        if isinstance(v, str):
            return [item.strip().lower() for item in v.split(",") if item.strip()]
        return v

    host: str = "0.0.0.0"
    port: int = 8888

    default_convert_timeout: int = 180


@lru_cache
def get_config():
    return Config()
