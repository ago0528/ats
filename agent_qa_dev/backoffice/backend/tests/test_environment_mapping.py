from app.core.enums import Environment
from app.core.environment import to_ats_environment


def test_env_mapping():
    assert to_ats_environment(Environment.DEV) == 'DV'
    assert to_ats_environment(Environment.ST2) == 'QA'
    assert to_ats_environment(Environment.ST) == 'ST'
    assert to_ats_environment(Environment.PR) == 'PR'
