from alembic.config import Config
from sqlalchemy.engine import make_url

from app.config import Settings


def test_database_credentials_round_trip_through_sqlalchemy_and_alembic():
    settings = Settings(
        _env_file=None,
        db_user="user@name",
        db_password="synthetic@:/?#%password",
        db_host="127.0.0.1",
        db_name="counselconnect_test",
    )
    config = Config()
    config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    for raw in (settings.database_url, config.get_main_option("sqlalchemy.url")):
        url = make_url(raw)
        assert url.username == settings.db_user
        assert url.password == settings.db_password
        assert url.host == settings.db_host
        assert url.database == settings.db_name
        assert url.query["charset"] == "utf8mb4"
