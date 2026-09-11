from __future__ import annotations

import pytest

from forgecode.model import _parse_arguments


def test_parse_arguments_accepts_json_object() -> None:
    assert _parse_arguments('{"path": "README.md"}') == {"path": "README.md"}


def test_parse_arguments_rejects_non_object() -> None:
    with pytest.raises(ValueError, match="JSON object"):
        _parse_arguments("[]")


def test_parse_arguments_rejects_invalid_json() -> None:
    with pytest.raises(ValueError, match="invalid tool arguments"):
        _parse_arguments("not-json")
