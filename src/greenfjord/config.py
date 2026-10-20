"""Load figure configuration files (independent of ``settings``, needs no ``.env``)."""

from pathlib import Path

import yaml


def get_script_name(script: str | Path) -> str:
    """Return ``<NAME>`` for a figure script ``plot_<NAME>.py``.

    Raises FileNotFoundError if the matching ``config_<NAME>.yaml`` does not
    exist next to the script. Call it with ``__file__``.
    """
    script = Path(script).resolve()
    name = script.stem.removeprefix("plot_")
    config = script.parent / f"config_{name}.yaml"
    if not config.exists():
        raise FileNotFoundError(f"No config for {script.name}: expected {config}")
    return name


def read_config(path: str | Path) -> dict:
    """Return the contents of the YAML file at ``path`` as a dict."""
    return yaml.safe_load(Path(path).read_text())
