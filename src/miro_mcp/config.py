from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Transport
    mcp_transport: Literal["stdio", "http"] = "stdio"
    mcp_http_port: int = 8080
    mcp_http_host: str = "0.0.0.0"

    # Auth mode:
    # "gateway" — production/SOP-compliant: access token from an HTTP header per request
    #             (no global state).
    # "env"     — local dev only: a single shared access token from an env var
    #             (not SOP-compliant).
    auth_mode: Literal["env", "gateway"] = "gateway"

    # Miro credentials (only required in env mode)
    miro_access_token: str | None = None

    # HTTP header name used to pass the access token in gateway mode.
    # The client must include this header on every /mcp request.
    miro_access_token_header: str = "X-Miro-Access-Token"

    # Miro's stable, documented REST API v2 base URL.
    miro_base_url: str = "https://api.miro.com/v2"

    @property
    def has_credentials(self) -> bool:
        """Returns True if the server can serve API calls.

        Gateway mode always returns True — each request carries its own credential.
        Env mode requires MIRO_ACCESS_TOKEN to be set.
        """
        if self.auth_mode == "gateway":
            return True
        return self.miro_access_token is not None


def get_settings() -> Settings:
    return Settings()
