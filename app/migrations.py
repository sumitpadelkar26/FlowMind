"""Small, additive schema upgrades for existing SQLite/PostgreSQL demo databases."""
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def upgrade_existing_database(engine: Engine) -> None:
    inspector = inspect(engine)
    if "action_items" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("action_items")}
    with engine.begin() as connection:
        if "priority" not in columns:
            connection.execute(text(
                "ALTER TABLE action_items ADD COLUMN priority VARCHAR(20) NOT NULL DEFAULT 'medium'"
            ))
        if "blocker" not in columns:
            connection.execute(text(
                "ALTER TABLE action_items ADD COLUMN blocker TEXT NOT NULL DEFAULT ''"
            ))
