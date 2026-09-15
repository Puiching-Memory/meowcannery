"""规则预设可以继承，书籍只覆盖与预设不同的规则。"""
import copy
import json
import re

from .catalog import ROOT


def merge_rules(base, override):
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_rules(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def load_preset(name, seen=()):
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        raise ValueError("预设名称只能包含小写字母、数字和下划线。")
    if name in seen:
        raise ValueError("预设循环继承：" + " -> ".join((*seen, name)))
    path = ROOT / "rules" / f"{name}.json"
    if not path.is_file():
        raise ValueError(f"找不到规则预设：{name}")
    rule = json.loads(path.read_text(encoding="utf-8"))
    parent = rule.pop("extends", None)
    return merge_rules(load_preset(parent, (*seen, name)), rule) if parent else rule


def book_rules(book):
    rules = merge_rules(load_preset(book.preset), book.rules)
    for key in ("chapter_pattern", "question_pattern", "answer_start", "quiz_start", "quiz_end", "answer_pattern"):
        if key == "answer_pattern" and key not in rules:
            continue
        try:
            re.compile(rules[key])
        except (KeyError, TypeError, re.error) as error:
            raise ValueError(f"{book.id} 的规则 {key} 无效：{error}") from error
    return rules
