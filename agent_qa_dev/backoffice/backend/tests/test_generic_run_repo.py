from app.core.db import SessionLocal
from app.core.enums import Environment
from app.repositories.generic_runs import GenericRunRepository


def test_repo_create_run_and_rows():
    db = SessionLocal()
    repo = GenericRunRepository(db)
    run = repo.create_run(Environment.DEV, {'k': 'v'})
    repo.add_rows(run.id, [{'ID': 'Q-1', '질의': 'hi'}])
    db.commit()
    assert repo.count_rows(run.id) == 1
    db.close()
