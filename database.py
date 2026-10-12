import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./redbasedagric.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    import models.order  # noqa: F401
    import models.product  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _add_missing_columns()


# create_all() only creates missing tables, not columns added to existing
# ones. Columns listed here are added in place if an older database lacks them.
_ADDED_COLUMNS = {
    "orders": {
        "delivery_fee_status": "VARCHAR(20)",
        "delivery_fee_paid_at": "TIMESTAMP",
    },
}


def _add_missing_columns():
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, columns in _ADDED_COLUMNS.items():
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, ddl_type in columns.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl_type}"))
