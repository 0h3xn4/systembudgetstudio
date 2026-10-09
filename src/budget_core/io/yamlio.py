"""YAML reading with line tracking, and canonical (deterministic) writing.

Reading uses ruamel.yaml round-trip mode only to learn line numbers; the result is converted to
plain Python. Errors never include file content (spec constraint 11).
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.constructor import DuplicateKeyError
from ruamel.yaml.error import YAMLError

Path = tuple[str | int, ...]


class YamlSyntaxError(Exception):
    """The file is not valid YAML. `line` is 1-based when known; the message holds no content."""

    def __init__(self, message: str, line: int | None) -> None:
        super().__init__(message)
        self.line = line


@dataclass
class LineMap:
    """1-based line numbers for every mapping key and sequence item."""

    _lines: dict[Path, int] = field(default_factory=dict)

    def lookup(self, path: Path) -> int | None:
        """Line of `path`, or of its nearest existing ancestor."""
        for end in range(len(path), -1, -1):
            line = self._lines.get(path[:end])
            if line is not None:
                return line
        return None


@dataclass
class LoadedYaml:
    data: Any
    lines: LineMap


def format_path(path: Path) -> str:
    out = ""
    for part in path:
        if isinstance(part, int):
            out += f"[{part}]"
        else:
            out += f".{part}" if out else str(part)
    return out


def _yaml() -> YAML:
    yaml = YAML(typ="rt")
    yaml.allow_duplicate_keys = False
    return yaml


def _convert(node: Any, path: Path, lines: dict[Path, int]) -> Any:
    if isinstance(node, CommentedMap):
        lines[path] = node.lc.line + 1
        out: dict[Any, Any] = {}
        for key in node:
            child = path + (key,)
            lines[child] = node.lc.key(key)[0] + 1
            out[key] = _convert(node[key], child, lines)
        return out
    if isinstance(node, CommentedSeq):
        seq: list[Any] = []
        for index, item in enumerate(node):
            child = path + (index,)
            lines[child] = node.lc.item(index)[0] + 1
            seq.append(_convert(item, child, lines))
        return seq
    if isinstance(node, bool) or node is None:
        return node
    if isinstance(node, int):
        return int(node)
    if isinstance(node, float):
        return float(node)
    if isinstance(node, str):
        return str(node)
    return node


def load_yaml_text(text: str) -> LoadedYaml:
    try:
        raw = _yaml().load(text)
    except DuplicateKeyError as exc:
        mark = exc.problem_mark
        raise YamlSyntaxError(
            "a field appears twice in the same mapping", mark.line + 1 if mark else None
        ) from None
    except YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        raise YamlSyntaxError(
            "the file is not valid YAML", mark.line + 1 if mark is not None else None
        ) from None
    lines: dict[Path, int] = {}
    data = _convert(raw, (), lines)
    return LoadedYaml(data, LineMap(lines))


def _to_commented(value: Any) -> Any:
    if isinstance(value, dict):
        cm = CommentedMap()
        for key, item in value.items():
            cm[key] = _to_commented(item)
        return cm
    if isinstance(value, list):
        cs = CommentedSeq()
        for item in value:
            cs.append(_to_commented(item))
        return cs
    return value


def dump_yaml(data: Any) -> str:
    """Canonical YAML: insertion-ordered keys, 2-space maps, indented sequences, LF, no comments."""
    yaml = YAML(typ="rt")
    yaml.default_flow_style = False
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.width = 4096
    yaml.preserve_quotes = False
    yaml.representer.add_representer(
        type(None), lambda rep, _data: rep.represent_scalar("tag:yaml.org,2002:null", "null")
    )
    buffer = io.StringIO()
    yaml.dump(_to_commented(data), buffer)
    return buffer.getvalue()
