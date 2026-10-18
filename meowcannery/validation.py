"""可同时用于解析结果、Excel 回读和导出前检查。"""
import re

TYPES = ("单选题", "多选题", "判断题", "填空题", "简答题")


def question_errors(q):
    errors = []
    for field, name in (("stem", "题干"), ("answer", "答案"), ("chapter", "章节")):
        if not isinstance(q.get(field), str) or not q[field].strip():
            errors.append(f"{name}为空或不是文本")
    kind = q.get("type")
    if kind not in TYPES:
        errors.append(f"不支持的题型：{kind}")
    options, answer = q.get("options", []), q.get("answer", "")
    if not isinstance(options, list) or any(not isinstance(o, str) for o in options):
        return errors + ["选项必须为文本列表"]
    if kind in TYPES[:2]:
        if not 2 <= len(options) <= 8 or any(not o.strip() for o in options):
            errors.append("选项数量须为 2–8，且不能有空选项")
        if len(set(o.strip() for o in options)) != len(options):
            errors.append("选项重复")
        if not isinstance(answer, str) or not re.fullmatch(r"[A-H]+", answer) or any(ord(c) - 65 >= len(options) for c in answer):
            errors.append("答案不在选项范围内")
        elif len(set(answer)) != len(answer):
            errors.append("答案字母重复")
        if kind == "单选题" and (not isinstance(answer, str) or len(answer) != 1):
            errors.append("单选题必须恰有一个答案")
    elif options:
        errors.append("非选择题不能携带选项")
    if kind == "判断题" and answer not in ("√", "×"):
        errors.append("判断题答案须为 √ 或 ×")
    for field in ("stem", "answer", "explanation", "chapter", "subject"):
        value = q.get(field, "")
        if isinstance(value, str) and (len(value) > 32767 or re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", value)):
            errors.append(f"{field} 超过 Excel 长度限制或含非法控制字符")
    if any(len(o) > 32767 or re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", o) for o in options):
        errors.append("选项超过 Excel 长度限制或含非法控制字符")
    return errors


def validate_bank(questions):
    if not questions:
        raise ValueError("题库为空，未生成或覆盖输出文件。")
    issues = []
    identities = set()
    for row, q in enumerate(questions, 2):
        prefix = f"第{row}行 {q.get('chapter', '')} {q.get('stem', '')[:50]}"
        issues.extend(prefix + "：" + error for error in question_errors(q))
        if "number" in q and "section" in q:
            key = (q.get("chapter"), q["section"], q["number"])
            if key in identities:
                issues.append(prefix + "：同章同节题号重复")
            identities.add(key)
    if issues:
        raise ValueError("题库校验失败，未覆盖输出文件：\n" + "\n".join(issues))
