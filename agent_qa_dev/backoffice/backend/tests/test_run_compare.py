import pytest

from app.core.db import SessionLocal
from app.core.enums import Environment, RunStatus
from app.models.generic_run_row import GenericRunRow
from app.repositories.generic_runs import GenericRunRepository
from app.services.run_compare import compare_runs


def test_compare_uses_latest_done_base_and_detects_changes():
    db = SessionLocal()
    repo = GenericRunRepository(db)

    base = repo.create_run(Environment.DEV, {})
    repo.add_rows(base.id, [{'ID': 'Q-1', '질의': 'q1'}])
    repo.set_status(base.id, RunStatus.DONE)

    current = repo.create_run(Environment.DEV, {})
    repo.add_rows(current.id, [{'ID': 'Q-1', '질의': 'q1'}])
    repo.set_status(current.id, RunStatus.DONE)
    db.commit()

    row = db.query(GenericRunRow).filter(GenericRunRow.run_id == current.id).first()
    row.logic_result = 'PASS: changed'
    db.commit()

    result = compare_runs(repo, current.id)
    assert result['baseRunId'] == base.id
    assert result['changedRows']
    db.close()


def test_compare_rejects_cross_environment_base():
    db = SessionLocal()
    repo = GenericRunRepository(db)

    dev_run = repo.create_run(Environment.DEV, {})
    repo.add_rows(dev_run.id, [{'ID': 'Q-1', '질의': 'q'}])
    repo.set_status(dev_run.id, RunStatus.DONE)

    pr_run = repo.create_run(Environment.PR, {})
    repo.add_rows(pr_run.id, [{'ID': 'Q-1', '질의': 'q'}])
    repo.set_status(pr_run.id, RunStatus.DONE)
    db.commit()

    with pytest.raises(PermissionError):
        compare_runs(repo, dev_run.id, pr_run.id)
    db.close()
