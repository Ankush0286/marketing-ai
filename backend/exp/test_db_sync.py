import os
import uuid
import libsql
from dotenv import load_dotenv
from sqlalchemy import create_engine, select, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

load_dotenv()

TURSO_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN")
LOCAL_DB_PATH = "local_db/local_auth.db"


# 1. Connection proxy to satisfy SQLAlchemy's pysqlite dialect
class LibsqlConnectionProxy:
    def __init__(self, raw_conn):
        self._raw_conn = raw_conn

    def create_function(self, *args, **kwargs):
        # Stub out create_function so SQLAlchemy's REGEXP setup doesn't crash
        pass

    def __getattr__(self, attr):
        # Forward all standard DB-API calls (cursor, commit, rollback, close, etc.)
        return getattr(self._raw_conn, attr)


def create_libsql_connection():
    raw_conn = libsql.connect(
        LOCAL_DB_PATH,
        sync_url=TURSO_URL,
        auth_token=TURSO_TOKEN,
    )
    return LibsqlConnectionProxy(raw_conn)


# 2. Sync helper to replicate between local disk and Turso Cloud
def sync_db():
    conn = libsql.connect(
        LOCAL_DB_PATH,
        sync_url=TURSO_URL,
        auth_token=TURSO_TOKEN,
    )
    conn.sync()
    conn.close()


# 3. SQLAlchemy Engine using the proxy creator
engine = create_engine(
    "sqlite://",
    creator=create_libsql_connection,
)


# 4. Declarative Models
class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)

    def __repr__(self) -> str:
        return f"<User(id='{self.id}', email='{self.email}')>"


# 5. Execution Test
if __name__ == "__main__":
    print("Syncing initial state from Turso Cloud...")
    sync_db()

    print("Creating tables locally...")
    Base.metadata.create_all(engine)

    print("Inserting user record...")
    with Session(engine) as session:
        new_user = User(
            id=str(uuid.uuid4()),
            email="ankush@example.com",
            password_hash="$argon2id$v=19$m=65536,t=3,p=4$dummy_hash",
        )
        session.add(new_user)
        session.commit()
        print(f"Created user: {new_user}")

    print("Syncing changes back to Turso Cloud...")
    sync_db()

    print("Reading user locally...")
    with Session(engine) as session:
        stmt = select(User).where(User.email == "ankush@example.com")
        user = session.scalars(stmt).first()
        if user:
            print(f"Found User in local replica: {user.email} (ID: {user.id})")