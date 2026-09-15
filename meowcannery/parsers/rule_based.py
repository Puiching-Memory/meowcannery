"""声明式章节习题解析器：独立题号空间、共用选项和集中/逐题答案。"""
import json
import re

from ..plugins import ParseResult
from ..text import plain_text, source_lines

OPTION = re.compile(r"(?<![A-Za-z\\])([A-H])[.、．:：)）]\s*")
RANGE = re.compile(r"[\[【（(]\s*(\d+)\s*[~～—–\-至]\s*(\d+)\s*[\]】）)]")
CHOICE_ANSWER = re.compile(r"(?<!\d)(\d+)\\?[.、．]\s*([A-H](?:[\s,，、]*[A-H])*)")
TYPES = dict(single="单选题", shared="单选题", multi="多选题", fill="填空题", judge="判断题",
             define="简答题", essay="简答题", calculate="简答题", discuss="简答题", translate="简答题",
             spectrum="简答题", essay_calculate="简答题")


def option_markers(text):
    """只按递增标号切分，保留 E. A、B、C、D 都正确 这样的选项内容。"""
    markers = []
    for match in OPTION.finditer(text):
        if not markers or match[1] > markers[-1][1]:
            markers.append(match)
    return markers


def parse(book, rules):
    result = ParseResult()
    bank, answers = {}, {}
    chapter, section, mode = "", "", ""
    current = answer_key = None
    pool, group_intro, intro = [], "", ""
    collecting, pending_range = False, None
    q_pattern = re.compile(rules["question_pattern"])
    a_pattern = re.compile(rules.get("answer_pattern", rules["question_pattern"]))
    chapters = sorted((int(p), title) for p, title in book.chapters.items())
    # 项目根目录从 catalog 获取，避免缓存深度影响路径。
    from ..catalog import ROOT
    corrections = ROOT / "corrections" / book.id / "source.json"
    fixes = json.loads(corrections.read_text(encoding="utf-8")) if corrections.exists() else []
    applied = set()
    from ..pipeline import required_pages
    selected_pages = set(required_pages(book))

    def issue(message, page, key=None):
        result.issues.append({"source": page, "chapter": key[0] if key else chapter, "section": key[1] if key else section,
                              "number": key[2] if key else None, "reason": message})

    def key_for(number):
        space = "choice" if rules.get("choice_numbering") == "continuous" and section in ("single", "shared", "multi") else section
        return chapter, space, number

    def is_unnumbered():
        return section in rules.get("unnumbered_sections", {}).get(chapter, [])

    def answer(number, value, page):
        nonlocal answer_key
        key = key_for(number)
        value = plain_text(value)
        if key in answers:
            issue(f"答案题号重复：{number}", page, key)
        else:
            answers[key] = [value, page]
        answer_key = key

    def range_answer(first, last, value, page):
        letters = re.sub(r"[\s,，、.。]", "", value)
        if last < first or len(letters) != last - first + 1 or not re.fullmatch(r"[A-H]+", letters):
            issue(f"共用选项答案区间 [{first}~{last}] 与答案数量不符：{value}", page)
            return
        for number, letter in zip(range(first, last + 1), letters):
            answer(number, letter, page)

    for path in sorted(book.cache.glob("p*.md")):
        if not re.fullmatch(r"p\d{4}\.md", path.name):
            continue
        page_number = int(path.stem[1:])
        if page_number not in selected_pages:
            continue
        mapped_chapter = next((name for first, name in reversed(chapters) if first <= page_number), "")
        if mapped_chapter and mapped_chapter != chapter:
            chapter, section, mode = mapped_chapter, "", ""
            current = answer_key = None
            pool, group_intro, intro, collecting, pending_range = [], "", "", False, None
        text = path.read_text(encoding="utf-8")
        for index, fix in enumerate(fixes):
            if fix["page"] == path.name:
                if text.count(fix["old"]) != 1:
                    raise ValueError(f"{path.name} 勘误原文不唯一或已变化：{fix['reason']}")
                text = text.replace(fix["old"], fix["new"], 1)
                applied.add(index)
        for raw in source_lines(text):
            s = raw.strip().lstrip("#").strip()
            s = re.sub(r"^\${1,2}\s*(?=\d+\.)", "", s)
            if not s or re.fullmatch(r"[-—·\s]*\d{1,4}[-—·\s]*", s):
                continue
            compact = re.sub(r"\s+", "", s).replace("**", "")
            if not chapters and re.fullmatch(rules["chapter_pattern"], s):
                chapter, section, mode = plain_text(s), "", ""
                current = answer_key = None
                pool, intro, group_intro, collecting, pending_range = [], "", "", False, None
                continue
            if re.fullmatch(rules["answer_start"], compact):
                mode, section, answer_key, pending_range = "answers", "", None, None
                current = None
                continue
            if re.fullmatch(rules["quiz_start"], compact):
                mode, section, current = "questions", "", None
                continue
            if re.fullmatch(rules["quiz_end"], compact):
                mode, section, current = "", "", None
                continue
            title = re.sub(r"^[一二三四五六七八九十0-9]+[、.．]\s*", "", compact)
            title = re.sub(r"[（(].*[)）]$", "", title)
            detected = rules["sections"].get(title)
            if detected:
                section = detected
                mode = mode or "questions"
                current = answer_key = None
                pool, intro, group_intro, collecting, pending_range = [], "", "", section == "shared", None
                continue
            if not chapter or not section or not mode:
                continue
            if raw.startswith("#") and not q_pattern.match(s):
                # 未知标题提示在报告中，避免章节切换时把理论内容挂到上一题。
                if "试题" in compact or "习题" in compact or "答案" in compact:
                    issue(f"未识别标题：{s}", path.name)
                    continue
            if mode == "answers":
                if section in ("single", "shared", "multi"):
                    s = plain_text(s)
                    s = re.sub(r"(?<!\d)(\d+)\s*[~～–-]\s*(\d+)\s*[.、．]", r"[\1~\2]", s)
                    matches = list(RANGE.finditer(s))
                    if matches:
                        for i, match in enumerate(matches):
                            end = matches[i+1].start() if i+1 < len(matches) else len(s)
                            body = s[match.end():end].strip()
                            first, last = map(int, match.groups())
                            if not body:
                                pending_range = (first, last)
                            else:
                                range_answer(first, last, body, path.name)
                        continue
                    if pending_range:
                        range_answer(*pending_range, s, path.name)
                        pending_range = None
                        continue
                    pairs = list(CHOICE_ANSWER.finditer(s))
                    for match in pairs:
                        answer(int(match[1]), re.sub(r"[\s,，、]", "", match[2]), path.name)
                    if not pairs and re.search(r"[A-H0-9]", s):
                        issue(f"未识别的选择题答案：{s[:160]}", path.name)
                    continue
                if section == "judge":
                    markers = list(re.finditer(r"(?<!\d)(\d+)[.、．]\s*(?=[√×xX对错]|正确|错误)", plain_text(s)))
                    if markers:
                        s = plain_text(s)
                        for index, marker in enumerate(markers):
                            end = markers[index+1].start() if index+1 < len(markers) else len(s)
                            answer(int(marker[1]), s[marker.end():end], path.name)
                        continue
                if section == "fill":
                    markers = list(re.finditer(r"(?:^|[。；;]\s*)([1-9]\d*)\\?[.、．]\s*", s))
                    if len(markers) > 1:
                        for index, marker in enumerate(markers):
                            end = markers[index+1].start() if index+1 < len(markers) else len(s)
                            answer(int(marker[1]), s[marker.end():end], path.name)
                        continue
                match = a_pattern.match(s)
                if match:
                    answer(int(match[1]), match[2], path.name)
                elif answer_key:
                    answers[answer_key][0] += "\n" + plain_text(s)
                elif is_unnumbered():
                    answer(1, s, path.name)
                else:
                    issue(f"没有题号的答案：{s[:100]}", path.name)
                continue
            if rules.get("inline_answers") and current:
                match = re.match(rules["inline_answer_pattern"], s)
                if match:
                    answer(current[2], match[1], path.name)
                    continue
                match = re.match(r"^(?:【解析】|解析[：:])\s*(.*)", s)
                if match:
                    bank[current]["explanation"] = plain_text(match[1])
                    continue
            if is_unnumbered() and not current:
                current = key_for(1)
                bank[current] = dict(stem=s, type=TYPES[section], options=[], chapter=chapter,
                                     section=section, number=1, source=path.name, answer="")
                continue
            if RANGE.fullmatch(plain_text(s)) and section == "shared":
                pool, group_intro, collecting, current = [], "", True, None
                continue
            match = q_pattern.match(s)
            if match:
                number, body = int(match[1]), match[2]
                # OCR 有时把下一组的 [4~8] 粘在上一题末尾。
                body = re.sub(r"\s*" + RANGE.pattern + r"\s*$", "", body)
                current = key_for(number)
                if current in bank:
                    issue(f"题号重复：{number}", path.name, current)
                    current = None
                    continue
                positions = option_markers(body) if section in ("single", "multi") else []
                # 题干里的 A、B、C 是组分枚举；行内选项只允许 A. / A: 等明确标号。
                if positions and (positions[0][1] != "A" or "、" in positions[0][0]):
                    positions = []
                options = []
                if positions:
                    options = [body[m.start():positions[i+1].start() if i+1 < len(positions) else len(body)]
                               for i, m in enumerate(positions)]
                    body = body[:positions[0].start()].strip()
                prefix = group_intro if section == "shared" else intro
                bank[current] = dict(stem=(prefix + "\n" if prefix else "") + body,
                                     type=TYPES[section], options=list(pool) if section == "shared" else options,
                                     chapter=chapter, section=current[1], number=number,
                                     source=path.name, answer="")
                collecting = False
                continue
            positions = option_markers(s) if section in ("single", "shared", "multi") else []
            if positions and not s[:positions[0].start()].strip():
                options = [s[m.start():positions[i+1].start() if i+1 < len(positions) else len(s)]
                           for i, m in enumerate(positions)]
                if section == "shared":
                    if positions[0][1] == "A" and not collecting:
                        pool, group_intro = [], ""
                    pool.extend(options)
                    collecting = True
                elif current:
                    bank[current]["options"].extend(options)
                else:
                    issue("没有对应题目的选项", path.name)
                continue
            if section == "shared" and collecting:
                # 共用选项之后的指令属于整组题干，不追加到最后一个选项。
                if re.match(r"^(?:试|请|判断|下列|以下|上述|根据|对于|各|为下列|要测定)", s) or "下列操作" in s:
                    group_intro = (group_intro + "\n" + s).strip()
                elif pool and not group_intro:
                    pool[-1] += " " + s
                else:
                    group_intro = (group_intro + "\n" + s).strip()
            elif current:
                q = bank[current]
                if q["options"] and section != "shared":
                    q["options"][-1] += "\n" + s
                else:
                    q["stem"] += "\n" + s
            else:
                intro = (intro + "\n" + s).strip()
    for key, q in bank.items():
        q["answer"], q["answer_source"] = answers.get(key, ["", ""])
        labels = "".join(OPTION.match(o)[1] if OPTION.match(o) else "?" for o in q["options"])
        if labels and labels != "ABCDEFGH"[:len(labels)]:
            issue(f"选项标号不连续：{labels}", q["source"], key)
            q.setdefault("review_reasons", []).append(f"选项标号不连续：{labels}")
        q["options"] = [plain_text(OPTION.sub("", o, count=1)) for o in q["options"]]
        q["stem"] = f"{q['number']}. " + plain_text(q["stem"])
        if q["type"] == "判断题":
            match = re.match(r"^(√|×|正确|错误|对|错|[xX])(?:[.。\s]*)(.*)$", q["answer"], re.S)
            if match:
                q["answer"] = "√" if match[1] in ("√", "对", "正确") else "×"
                if match[2]:
                    q["explanation"] = match[2].strip()
        q["subject"] = book.subject
        result.questions.append(q)
    for key in answers.keys() - bank.keys():
        result.issues.append(dict(chapter=key[0], section=key[1], number=key[2],
                                 source=answers[key][1], reason="答案没有对应题目"))
    missing_fixes = set(range(len(fixes))) - applied
    if missing_fixes:
        raise ValueError("部分原文勘误没有匹配页面：" + str(sorted(missing_fixes)))
    return result
