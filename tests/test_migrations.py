from sqlalchemy import create_engine, inspect, text

from app.migrations import upgrade_existing_database


def test_old_action_items_table_gets_additive_fields(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE action_items (id INTEGER PRIMARY KEY, title VARCHAR(300))"))
        connection.execute(text("INSERT INTO action_items (id, title) VALUES (1, 'legacy task')"))

    upgrade_existing_database(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("action_items")}
    assert {"priority", "blocker"} <= columns
    with engine.connect() as connection:
        row = connection.execute(text("SELECT priority, blocker FROM action_items WHERE id = 1")).one()
    assert row == ("medium", "")
    engine.dispose()
