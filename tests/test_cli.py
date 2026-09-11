from __future__ import annotations

from forgecode.cli import build_parser


def test_task_is_optional_for_interactive_mode() -> None:
    args = build_parser().parse_args([])

    assert args.task is None
    assert args.interactive is False

    explicit = build_parser().parse_args(["--interactive"])

    assert explicit.task is None
    assert explicit.interactive is True
