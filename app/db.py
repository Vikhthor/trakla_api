from sqlmodel import Session, SQLModel, create_engine, select, col, or_, func, case
from sqlalchemy import MetaData
from .models import *
from alembic import command
from alembic.config import Config
from .config import get_settings

settings = get_settings()

def run_migrations():
    cfg = Config("alembic.ini")
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")

# class Settings(BaseSettings):
#     app_name: str = "Awesome API"
#     admin_email: str
#     items_per_user: int = 50

#     model_config = SettingsConfigDict(env_file=".env")

connect_args = {
    # "check_same_thread": False
}
connection_uri = "sqlite:///database.db"
db_host = settings.db_host
db_name = settings.db_name
db_user = settings.db_user
db_password = settings.db_password
if db_host:
    connection_uri = f"mysql+pymysql://{db_user}:{db_password}@{db_host}/{db_name}?charset=utf8mb4"

engine = create_engine(connection_uri, connect_args=connect_args)

naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}
SQLModel.metadata.naming_convention = naming_convention

def create_db_and_tables(): # call in main.py
    SQLModel.metadata.create_all(engine)
    # run_migrations()

async def get_db():
    db = Session(engine)
    try:
        yield db
    finally:
        db.close()

class Db:
    """
    Context manager for handling code coverage.

    This class sets up code coverage measurement for a specific app,
    applying the appropriate inclusion and exclusion patterns.
    """

    def __init__(self):
        pass

    def insert(self, data):
        """
        Insert new record in DB
        """
        # session = Session(engine)
        # session.add(data)
        # session.add(data_2)
        # session.commit()
        # session.close()

        with Session(engine) as session:
            session.add(data)
            # session.add(data_2)
            session.commit()
            # session.refresh(data) # explicitly refresh object with new data.
        return data

    def update(self, data):
        """Update existing record"""
        with Session(engine) as session:
            session.add(data)
            session.commit()
        return data

    def get(self, model, filters: str | int | float | list, or_filters: dict | None = {}):
        """
        Get single record in DB
        """
        with Session(engine) as session:
            result = None
            if isinstance(filters, dict):
                query_filters = self.parse_filters(model, filters)
                or_query_filters = {}
                if or_filters:
                    or_query_filters = self.parse_filters(model, or_filters)
                statement = select(model).where(*query_filters, or_(*or_query_filters))
                result = session.exec(statement).first()
            else:
                result = session.get(model, filters)
            # result = session.exec(statement).one() # throws error if multiple records or no records exists
        return result

    def get_all(self, model):
        """
        Get all records in DB
        """
        with Session(engine) as session:
            statement = select(model).where(model.name == "Spider-Boy")
            hero = session.exec(statement).all()
        return hero

    @classmethod
    def parse_filters(self, model, filters):
        query_filters = []
        for k, v in filters.items():
            if isinstance(v, str | int | bool | float):
                query_filters.append(getattr(model,k) == v)
            elif isinstance(v, list):
                cond, value = v
                if cond in ['=', '==']:
                    query_filters.append(getattr(model,k) == value)
                elif cond == '>':
                    query_filters.append(getattr(model,k) > value)
                elif cond == '>=':
                    query_filters.append(getattr(model,k) >= value)
                elif cond == '<':
                    query_filters.append(getattr(model,k) < value)
                elif cond == '<=':
                    query_filters.append(getattr(model,k) <= value)
                elif cond == 'in':
                    query_filters.append(col(getattr(model,k)).in_(list(value)))
                elif cond == 'between':
                    query_filters.append(getattr(model,k) >= value[0])
                    query_filters.append(getattr(model,k) <= value[1])
        return query_filters

def get_count(model: SQLModel, session, filters = {}):
    # pylint: disable=not-callable
    query_filters = Db.parse_filters(model, filters)
    stmt = select(func.count(model.id)).where(*query_filters)
    return session.execute(stmt).scalar()

if __name__ == "__main__": # run uv run python db.py to create db and tables
    create_db_and_tables()