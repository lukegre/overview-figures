import pathlib
from functools import partial
from typing import Literal

import munch
import yaml
from loguru import logger


class PrettyMunch(munch.Munch):
    """A Munch subclass that pretty prints its contents."""

    def __repr__(self) -> str:
        max_display_length = 110

        header = f"<PrettyMunch with {len(self)} keys>\n"

        yaml_string = yaml.dump(self.toDict(), allow_unicode=True, default_flow_style=False, indent=3)
        yaml_string_truncated = "\n".join(
            line if len(line) <= max_display_length else line[:max_display_length] + "..."
            for line in yaml_string.splitlines()
        )
        return header + yaml_string_truncated


def read_yaml_source(
    path: str, yaml_path_as_parent: bool = True, errors: Literal["ignore", "warn", "raise"] = "warn", **kwargs
) -> PrettyMunch:
    """
    Read a YAML source file and return its contents as a Munch object.

    Args:
        path (str): The path to the YAML file.
        yaml_path_as_parent (bool): Whether the paths in the YAML file are relative to the YAML file.
        errors (str): How to handle errors when prepending YAML path. Options are 'ignore', 'warn', 'raise'.
        **kwargs: variables to replace in the YAML file using Jinja2 templating.
    """
    with open(path, "r") as file:
        yaml_str = file.read()
    if kwargs != {}:
        yaml_str = process_template(yaml_str, **kwargs)
    # Load YAML string data
    data = yaml.safe_load(yaml_str)

    data: PrettyMunch = munch.munchify(data, factory=PrettyMunch)  # type: ignore

    if yaml_path_as_parent:
        prepend_yaml_path_func = partial(prepend_yaml_path, yaml_path=path, errors=errors)
        data = apply_func_to_nested_dict(data, prepend_yaml_path_func)  # type: ignore
        for key in data.keys():
            path = data[key]

    return data


def process_template(template_str: str, **kwargs) -> str:
    """Process a Jinja2 template string with the given keyword arguments."""
    from jinja2 import Template

    template = Template(template_str)
    rendered_str = template.render(**kwargs)
    return rendered_str


def apply_func_to_nested_dict(d: dict | PrettyMunch, func) -> dict | PrettyMunch:
    """Recursively apply a function to all values in a nested dictionary."""
    for key, value in d.items():
        if isinstance(value, dict):
            d[key] = apply_func_to_nested_dict(value, func)
        else:
            d[key] = func(value)
    return d


def make_path_if_exists(path: str | pathlib.Path) -> pathlib.Path | str:
    """Return a pathlib.Path object if the path exists, otherwise return None."""
    p = pathlib.Path(path)
    if p.exists():
        return p
    return path


def prepend_yaml_path(
    path: str | pathlib.Path, yaml_path: str, errors: Literal["ignore", "warn", "raise"] = "warn"
) -> str:
    """Prepend the parent directory of the yaml path to the path."""
    if str(path).startswith("./"):
        p = pathlib.Path(path)
        yaml_dir = pathlib.Path(yaml_path).parent
        full_path = yaml_dir / p
        try:
            # Test if the path exists
            assert pathlib.Path(full_path).exists(), f"Path does not exist: {full_path}"
        except AssertionError as e:
            if errors == "ignore":
                pass
            elif errors == "warn":
                logger.warning(str(e))
            elif errors == "raise":
                raise e

        return str(full_path)
    else:
        return str(path)
