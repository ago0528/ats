from fastapi.testclient import TestClient

from app.main import app


def test_validation_settings_get_and_patch():
    client = TestClient(app)

    get_resp = client.get("/api/v1/validation-settings/dev")
    assert get_resp.status_code == 200
    assert get_resp.json()["environment"] == "dev"
    assert get_resp.json()["repeatInConversationDefault"] == 1
    assert get_resp.json()["paginationPageSizeLimitDefault"] == 100

    patch_resp = client.patch(
        "/api/v1/validation-settings/dev",
        json={
            "repeatInConversationDefault": 2,
            "conversationRoomCountDefault": 3,
            "agentParallelCallsDefault": 4,
            "timeoutMsDefault": 90000,
            "testModelDefault": "gpt-4o",
            "evalModelDefault": "gpt-5.2",
            "paginationPageSizeLimitDefault": 180,
        },
    )
    assert patch_resp.status_code == 200
    body = patch_resp.json()
    assert body["repeatInConversationDefault"] == 2
    assert body["conversationRoomCountDefault"] == 3
    assert body["agentParallelCallsDefault"] == 4
    assert body["timeoutMsDefault"] == 90000
    assert body["testModelDefault"] == "gpt-4o"
    assert body["paginationPageSizeLimitDefault"] == 180
