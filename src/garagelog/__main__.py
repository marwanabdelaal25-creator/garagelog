"""Allow `python -m garagelog` invocation."""

from garagelog.cli import main

__doc__ = """
Entry point for the garagelog CLI.

Examples:
  python -m garagelog init
  python -m garagelog vehicle-add "Monstera" --make monstera-deliciosa
  python -m garagelog service <vehicle-id> --amount 250ml
  python -m garagelog schedule --week
  python -m garagelog export garage.json

Environment:
  GARAGELOG_HOME  Directory for default garage.json (default: ~/.garagelog/)
"""

if __name__ == "__main__":
    raise SystemExit(main())
