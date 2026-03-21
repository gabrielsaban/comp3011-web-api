from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str
    test_database_url: str = ""

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    app_env: str = "development"
    cache_preload_on_startup: bool = True

    cors_allow_origins: str = ""
    cors_allow_credentials: bool = False
    cors_allow_methods: str = "GET,POST,PATCH,DELETE,OPTIONS"
    cors_allow_headers: str = "*"

    stats19_data_path: str = ""
    lad_lookup_csv_path: str = ""
    midas_hourly_weather_path: str = ""
    midas_hourly_rain_path: str = ""
    import_year_from: int = 2019
    import_year_to: int = 2023


settings = Settings()
