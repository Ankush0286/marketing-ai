from sqlalchemy.orm import (
    DeclarativeBase,
    declared_attr,
)

class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy declarative models.
    Automatically generates lowercase __tablename__ from class name.
    """

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return f"{cls.__name__.lower()}s"

    def __repr__(self):
        return f"<{self.__class__.__name__} id={getattr(self, 'id', 'Unsaved')}>"

