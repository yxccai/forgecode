"""Allow ``python -m forgecode`` to use the same CLI as ``forge``."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
