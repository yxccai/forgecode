from __future__ import annotations

import pytest

from forgecode.model import _parse_arguments, create_langchain_chat_model


def test_parse_arguments_accepts_json_object() -> None:
    assert _parse_arguments('{"path": "README.md"}') == {"path": "README.md"}


def test_parse_arguments_rejects_non_object() -> None:
    with pytest.raises(ValueError, match="JSON object"):
        _parse_arguments("[]")


def test_parse_arguments_rejects_invalid_json() -> None:
    with pytest.raises(ValueError, match="invalid tool arguments"):
        _parse_arguments("not-json")


def test_langchain_factory_accepts_explicit_third_party_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FORGECODE_API_KEY", "environment-key")
    monkeypatch.setenv("FORGECODE_BASE_URL", "https://environment.example/v1")

    model = create_langchain_chat_model(
        model="third-party-model",
        api_key="explicit-key",
        base_url="https://provider.example/v1",
    )

    assert model.model_name == "third-party-model"
    assert model.openai_api_key.get_secret_value() == "explicit-key"
    assert str(model.openai_api_base) == "https://provider.example/v1"


def test_langchain_factory_reads_project_environment_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_BASE", raising=False)
    monkeypatch.setenv("FORGECODE_API_KEY", "project-key")
    monkeypatch.setenv("FORGECODE_BASE_URL", "https://provider.example/v1")

    model = create_langchain_chat_model(model="third-party-model")

    assert model.openai_api_key.get_secret_value() == "project-key"
    assert str(model.openai_api_base) == "https://provider.example/v1"
