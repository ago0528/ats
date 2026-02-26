import io

from fastapi.testclient import TestClient

from app.main import app


def test_validation_queries_crud_and_bulk_upload():
    client = TestClient(app)

    template_resp = client.get("/api/v1/queries/template")
    assert template_resp.status_code == 200
    assert "text/csv" in template_resp.headers.get("content-type", "")
    assert "attachment; filename=\"query_template.csv\"" == template_resp.headers.get("content-disposition")
    assert (
        "질의,카테고리,그룹,targetAssistant,contextJson,기대 결과,Logic 검증 필드,Logic 기대값,latencyClass"
        in template_resp.content.decode("utf-8-sig")
    )

    group_resp = client.post("/api/v1/query-groups", json={"groupName": "지원자 관리", "description": "그룹"})
    group_id = group_resp.json()["id"]

    create_resp = client.post(
        "/api/v1/queries",
        json={
            "queryText": "서울 강남 개발자 채용 공고 보여줘",
            "expectedResult": "채용 공고 리스트",
            "category": "Happy path",
            "groupId": group_id,
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

    test_set_resp = client.post(
        "/api/v1/validation-test-sets",
        json={
            "name": "질의 사용 테스트 세트",
            "queryIds": [query_id],
        },
    )
    assert test_set_resp.status_code == 200

    list_resp = client.get("/api/v1/queries")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1
    assert list_resp.json()["items"][0]["testSetUsage"]["count"] == 1
    assert list_resp.json()["items"][0]["testSetUsage"]["testSetNames"] == ["질의 사용 테스트 세트"]

    filtered_resp = client.get(f"/api/v1/queries?queryIds={query_id}")
    assert filtered_resp.status_code == 200
    assert filtered_resp.json()["total"] == 1
    assert filtered_resp.json()["items"][0]["id"] == query_id

    patch_resp = client.patch(f"/api/v1/queries/{query_id}", json={"category": "Edge case"})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["category"] == "Edge case"

    csv_body = (
        "질의,카테고리,그룹,targetAssistant,contextJson,기대 결과,Logic 검증 필드,Logic 기대값,latencyClass\n"
        "질의1,Happy path,,,,,,,\n"
        f'질의2,Adversarial input,{group_id},ORCHESTRATOR_WORKER_V3,"{{""recruitPlanId"":123}}",기대 결과 2,assistantMessage,채용,MULTI\n'
        "질의3,Edge case,지원자 관리,,,,,,\n"
        "질의4,Edge case,없는그룹,,,,,,\n"
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
    assert by_text["질의1"]["expectedResult"] == ""
    assert by_text["질의1"]["logicFieldPath"] == ""
    assert by_text["질의1"]["logicExpectedValue"] == ""
    assert by_text["질의2"]["groupId"] == group_id
    assert by_text["질의2"]["targetAssistant"] == "ORCHESTRATOR_WORKER_V3"
    assert by_text["질의2"]["contextJson"] == '{"recruitPlanId":123}'
    assert by_text["질의2"]["expectedResult"] == "기대 결과 2"
    assert by_text["질의2"]["logicFieldPath"] == "assistantMessage"
    assert by_text["질의2"]["logicExpectedValue"] == "채용"
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


def test_validation_queries_bulk_update_preview_and_apply():
    client = TestClient(app)

    source_group_resp = client.post("/api/v1/query-groups", json={"groupName": "원본그룹", "description": "기본 그룹"})
    assert source_group_resp.status_code == 200
    source_group_id = source_group_resp.json()["id"]

    first_query_resp = client.post(
        "/api/v1/queries",
        json={
            "queryText": "업데이트 대상 질의",
            "expectedResult": "기존 기대값",
            "category": "Happy path",
            "groupId": source_group_id,
            "logicFieldPath": "assistantMessage",
            "logicExpectedValue": "기존값",
            "targetAssistant": "ORCHESTRATOR_WORKER_V3",
            "contextJson": "{\"phase\":\"old\"}",
        },
    )
    assert first_query_resp.status_code == 200
    first_query_id = first_query_resp.json()["id"]

    second_query_resp = client.post(
        "/api/v1/queries",
        json={
            "queryText": "변경 없음 질의",
            "expectedResult": "유지",
            "category": "Edge case",
            "groupId": source_group_id,
            "logicFieldPath": "assistantMessage",
            "logicExpectedValue": "유지값",
            "targetAssistant": "ORCHESTRATOR_WORKER_V3",
            "contextJson": "{\"phase\":\"keep\"}",
        },
    )
    assert second_query_resp.status_code == 200
    second_query_id = second_query_resp.json()["id"]

    usage_set_resp = client.post(
        "/api/v1/validation-test-sets",
        json={
            "name": "업데이트 사용 세트",
            "queryIds": [first_query_id, second_query_id],
        },
    )
    assert usage_set_resp.status_code == 200

    csv_body = (
        "쿼리 ID,질의,카테고리,그룹,targetAssistant,contextJson,기대 결과,Logic 검증 필드,Logic 기대값\n"
        f'{first_query_id},업데이트 완료 질의,Adversarial input,새그룹,NEW_ASSISTANT,"{{""phase"":""new""}}",신규 기대값,assistantMessage,신규값\n'
        f'{second_query_id},변경 없음 질의,Edge case,원본그룹,ORCHESTRATOR_WORKER_V3,"{{""phase"":""keep""}}",유지,assistantMessage,유지값\n'
        ",누락행,Happy path,,,,,,\n"
        "unknown-query-id,매핑 실패 질의,Happy path,,,,,,\n"
        f"{first_query_id},중복 행,Happy path,,,,,,\n"
    )

    preview_resp = client.post(
        "/api/v1/queries/bulk-update/preview",
        files={"file": ("queries-update.csv", io.BytesIO(csv_body.encode("utf-8")), "text/csv")},
    )
    assert preview_resp.status_code == 200
    preview_json = preview_resp.json()
    assert preview_json["totalRows"] == 5
    assert preview_json["plannedUpdateCount"] == 1
    assert preview_json["unchangedCount"] == 1
    assert preview_json["unmappedQueryCount"] == 1
    assert preview_json["missingQueryIdRows"] == [3]
    assert preview_json["duplicateQueryIdRows"] == [5]
    assert preview_json["unmappedQueryRows"] == [4]
    assert preview_json["unmappedQueryIds"] == ["unknown-query-id"]
    assert preview_json["groupsToCreate"] == ["새그룹"]
    assert preview_json["groupsToCreateRows"] == [1]
    assert any(row["status"] == "planned-update" and row["queryId"] == first_query_id for row in preview_json["previewRows"])
    assert any(row["status"] == "unmapped-query-id" and row["queryId"] == "unknown-query-id" for row in preview_json["previewRows"])

    blocked_group_resp = client.post(
        "/api/v1/queries/bulk-update",
        data={"allowCreateGroups": "false", "skipUnmappedQueryIds": "false"},
        files={"file": ("queries-update.csv", io.BytesIO(csv_body.encode("utf-8")), "text/csv")},
    )
    assert blocked_group_resp.status_code == 400

    blocked_unmapped_resp = client.post(
        "/api/v1/queries/bulk-update",
        data={"allowCreateGroups": "true", "skipUnmappedQueryIds": "false"},
        files={"file": ("queries-update.csv", io.BytesIO(csv_body.encode("utf-8")), "text/csv")},
    )
    assert blocked_unmapped_resp.status_code == 400

    apply_resp = client.post(
        "/api/v1/queries/bulk-update",
        data={"allowCreateGroups": "true", "skipUnmappedQueryIds": "true"},
        files={"file": ("queries-update.csv", io.BytesIO(csv_body.encode("utf-8")), "text/csv")},
    )
    assert apply_resp.status_code == 200
    apply_json = apply_resp.json()
    assert apply_json["requestedRowCount"] == 5
    assert apply_json["updatedCount"] == 1
    assert apply_json["unchangedCount"] == 1
    assert apply_json["skippedUnmappedCount"] == 1
    assert apply_json["skippedMissingIdCount"] == 1
    assert apply_json["skippedDuplicateQueryIdCount"] == 1
    assert apply_json["createdGroupNames"] == ["새그룹"]

    listed_resp = client.get("/api/v1/queries")
    assert listed_resp.status_code == 200
    listed = listed_resp.json()["items"]
    by_id = {item["id"]: item for item in listed}
    assert by_id[first_query_id]["queryText"] == "업데이트 완료 질의"
    assert by_id[first_query_id]["category"] == "Adversarial input"
    assert by_id[first_query_id]["groupName"] == "새그룹"
    assert by_id[first_query_id]["targetAssistant"] == "NEW_ASSISTANT"
    assert by_id[first_query_id]["contextJson"] == '{"phase":"new"}'
    assert by_id[first_query_id]["expectedResult"] == "신규 기대값"
    assert by_id[first_query_id]["logicExpectedValue"] == "신규값"
    assert by_id[first_query_id]["testSetUsage"]["count"] == 1
    assert by_id[first_query_id]["testSetUsage"]["testSetNames"] == ["업데이트 사용 세트"]

    assert by_id[second_query_id]["queryText"] == "변경 없음 질의"
    assert by_id[second_query_id]["expectedResult"] == "유지"
