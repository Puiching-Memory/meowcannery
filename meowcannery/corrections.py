"""原文和题目勘误的统一存储；每次应用都验证原值。"""
import json
from copy import deepcopy
from pathlib import Path


def apply_question_fixes(questions, path):
    path = Path(path)
    if not path.exists():
        return questions
    questions = deepcopy(questions)
    for fix in json.loads(path.read_text(encoding="utf-8")):
        matches = [q for q in questions if all(q.get(k) == v for k, v in fix["match"].items())]
        if len(matches) != 1:
            raise ValueError(f"题目勘误匹配数为 {len(matches)}：{fix['match']}")
        q = matches[0]
        if any(q.get(k) != v for k, v in fix["before"].items()):
            raise ValueError(f"勘误原文已变化：{fix['match']}")
        q.update(fix["after"])
        explanation = fix["reason"]
        if fix.get("sources"):
            explanation += "\n依据：" + "；".join(fix["sources"])
        q["explanation"] = (q.get("explanation", "") + "\n" + explanation).strip()
    return questions
