from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """
    Unified DeclarativeBase class for all SQLAlchemy database models.
    Provides standard ORM capabilities and registry for auto-migrations.
    """
    pass
