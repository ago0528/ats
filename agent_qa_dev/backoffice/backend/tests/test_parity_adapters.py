from app.adapters.prompt_api_adapter import PromptApiAdapter


def test_workers_contract_exists():
    workers = PromptApiAdapter.workers()
    assert isinstance(workers, list)
    assert workers
    first = workers[0]
    assert 'workerType' in first
    assert 'description' in first
