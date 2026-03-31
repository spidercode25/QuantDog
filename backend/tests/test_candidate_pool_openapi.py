from __future__ import annotations


import yaml


def test_openapi_json_includes_candidate_pool_and_telegram(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    from api import create_app

    app = create_app()
    client = app.test_client()

    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200

    data = response.get_json()
    assert "/api/v1/candidate-pools/latest" in data["paths"]
    assert "/api/v1/telegram/messages" in data["paths"]
    assert data["paths"]["/api/v1/candidate-pools/latest"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/CandidatePoolLatestResponse"
    assert data["paths"]["/api/v1/telegram/messages"]["post"]["responses"]["202"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/TelegramMessageEnqueueResponse"
    request_body = data["paths"]["/api/v1/telegram/messages"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    assert request_body["required"] == ["chat_id", "text"]
    assert "dedupe_key" not in request_body["properties"]
    parameter_names = [parameter["name"] for parameter in data["paths"]["/api/v1/telegram/messages"]["post"]["parameters"]]
    assert parameter_names == ["Authorization", "X-Telegram-Api-Token", "Idempotency-Key"]
    candidate_schema = data["components"]["schemas"]["CandidatePoolLatestResponse"]["properties"]["data"]["properties"]
    assert list(candidate_schema.keys()) == ["candidates"]


def test_static_openapi_yaml_includes_candidate_pool_and_telegram_paths():
    with open("openapi.yaml", "r", encoding="utf-8") as handle:
        doc = yaml.safe_load(handle)

    assert "/api/v1/candidate-pools/latest" in doc["paths"]
    assert "/api/v1/telegram/messages" in doc["paths"]
    assert doc["paths"]["/api/v1/candidate-pools/latest"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/CandidatePoolLatestResponse"
    assert doc["paths"]["/api/v1/telegram/messages"]["post"]["responses"]["202"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/TelegramMessageEnqueueResponse"
    yaml_parameter_names = [parameter["name"] for parameter in doc["paths"]["/api/v1/telegram/messages"]["post"]["parameters"]]
    assert yaml_parameter_names == ["Authorization", "X-Telegram-Api-Token", "Idempotency-Key"]
    assert "dedupe_key" not in doc["paths"]["/api/v1/telegram/messages"]["post"]["requestBody"]["content"]["application/json"]["schema"]["properties"]
