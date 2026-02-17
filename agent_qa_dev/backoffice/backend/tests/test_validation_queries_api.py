import io

from fastapi.testclient import TestClient

from app.main import app


def test_validation_queries_crud_and_bulk_upload():
    client = TestClient(app)

    template_resp = client.get("/api/v1/queries/template")
    assert template_resp.status_code == 200
    assert "text/csv" in template_resp.headers.get("content-type", "")
    assert "attachment; filename=\"query_template.csv\"" == template_resp.headers.get("content-disposition")
    assert "질의,카테고리,그룹" in template_resp.content.decode("utf-8-sig")

    group_resp = client.post("/api/v1/query-groups", json={"groupName": "지원자 관리", "description": "그룹"})
    group_id = group_resp.json()["id"]

    create_resp = client.post(
        "/api/v1/queries",
        json={
            "queryText": "서울 강남 개발자 채용 공고 보여줘",
            "expectedResult": "채용 공고 리스트",
            "category": "Happy path",
            "groupId": group_id,
            "llmEvalCriteria": {"version": 1},
            "logicFieldPath": "assistantMessage",
            "logicExpectedValue": "채용",
            "targetAssistant": "ORCHESTRATOR_WORKER_V3",
            "contextJson": "{\"recruitPlanId\": 123}",
        },
    )
    assert create_resp.status_code == 200
    assert create_resp.json()["targetAssistant"] == "ORCHESTRATOR_WORKER_V3"
    assert create_resp.json()["contextJson"] == "{\"recruitPlanId\": 123}"
    query_id = create_resp.json()["id"]

    list_resp = client.get("/api/v1/queries")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    filtered_resp = client.get(f"/api/v1/queries?queryIds={query_id}")
    assert filtered_resp.status_code == 200
    assert filtered_resp.json()["total"] == 1
    assert filtered_resp.json()["items"][0]["id"] == query_id

    patch_resp = client.patch(f"/api/v1/queries/{query_id}", json={"category": "Edge case"})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["category"] == "Edge case"

    csv_body = (
        "질의,카테고리,그룹\n"
        "질의1,Happy path,\n"
        f"질의2,Adversarial input,{group_id}\n"
        "질의3,Edge case,지원자 관리\n"
        "질의4,Edge case,없는그룹\n"
    )
    preview_resp = client.post(
        "/api/v1/queries/bulk-upload/preview",
        files={"file": ("queries.csv", io.BytesIO(csv_body.encode("utf-8")), "text/csv")},
    )
    assert preview_resp.status_code == 200
    assert preview_resp.json()["groupsToCreate"] == ["없는그룹"]
    assert preview_resp.json()["groupsToCreateRows"] == [4]

    bulk_resp = client.post(
        "/api/v1/queries/bulk-upload",
        data={"createdBy": "tester"},
        files={"file": ("queries.csv", io.BytesIO(csv_body.encode("utf-8")), "text/csv")},
    )
    assert bulk_resp.status_code == 200
    assert bulk_resp.json()["createdCount"] == 4
    assert bulk_resp.json()["invalidRows"] == []
    assert bulk_resp.json()["createdGroupNames"] == ["없는그룹"]

    listed = client.get("/api/v1/queries").json()["items"]
    by_text = {item["queryText"]: item for item in listed}
    assert by_text["질의1"]["groupId"] is None
    assert by_text["질의2"]["groupId"] == group_id
    assert by_text["질의3"]["groupId"] == group_id
    assert by_text["질의4"]["groupName"] == "없는그룹"

    multi_filter_resp = client.get(f"/api/v1/queries?category=Edge case,Adversarial input&groupId={group_id}")
    assert multi_filter_resp.status_code == 200
    filtered_items = multi_filter_resp.json()["items"]
    filtered_texts = {item["queryText"] for item in filtered_items}
    assert filtered_texts == {"서울 강남 개발자 채용 공고 보여줘", "질의2", "질의3"}

    bom_csv_body = "\ufeff질의,카테고리,그룹\nBOM 질의,Happy path,\n"
    bom_bulk_resp = client.post(
        "/api/v1/queries/bulk-upload",
        data={"createdBy": "tester"},
        files={"file": ("queries-bom.csv", io.BytesIO(bom_csv_body.encode("utf-8")), "text/csv")},
    )
    assert bom_bulk_resp.status_code == 200
    assert bom_bulk_resp.json()["createdCount"] == 1

    delete_resp = client.delete(f"/api/v1/queries/{query_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["ok"] is True
