"""内置插件、项目 plugins 目录和第三方 entry point 的统一入口。"""
from dataclasses import dataclass, field
from importlib import import_module
from importlib.metadata import entry_points
import re


@dataclass
class ParseResult:
    questions: list = field(default_factory=list)
    issues: list = field(default_factory=list)


BUILTINS = {
    "pharmacology": "meowcannery.parsers.pharmacology:parse",
    "rule_based": "meowcannery.parsers.rule_based:parse",
}


def load_plugin(name):
    """插件约定：parse(book, rules) -> ParseResult。不修改公共流程。"""
    if name in BUILTINS:
        module, attribute = BUILTINS[name].split(":")
        return getattr(import_module(module), attribute)
    for entry in entry_points(group="meowcannery.plugins"):
        if entry.name == name:
            return entry.load()
    if re.fullmatch(r"[a-z][a-z0-9_]*", name):
        try:
            return import_module(f"plugins.{name}").parse
        except ModuleNotFoundError as error:
            if error.name not in ("plugins", f"plugins.{name}"):
                raise
    raise ValueError(f"未找到插件 {name!r}。内置插件：" + "、".join(BUILTINS))
