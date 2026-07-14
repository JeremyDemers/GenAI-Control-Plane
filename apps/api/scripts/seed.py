from app.core.database import Base, SessionLocal, engine
from app.models import entities  # noqa: F401
from app.services.seed import seed_development_data


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_development_data(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
