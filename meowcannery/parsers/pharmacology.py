# -*- coding: utf-8 -*-
"""药理学书籍插件：保留经原页及反馈验证的题目解析规则。"""
import json
import re
from pathlib import Path

from ..catalog import get_book


SEC_KEYWORDS = (("单选题", "choice"), ("多选题", "choice"), ("选择题", "choice"),
                ("填空", "fill"), ("对译", "trans"), ("名词解释", "define"),
                ("问答", "essay"), ("简答", "essay"), ("论述", "discuss"))
Q_START = re.compile(r"(\d+)\\?[.、]\s*(.+)")
Q_SPLIT_INLINE = re.compile(r"(?<!\d)\s*(?=\d+\\?[.、](?!\d)\s*\S)")
OPT_PREFIX = re.compile(r"^\s*[A-E]\\?[.、．:：)）]\s*")
OPT_BOUNDARY = re.compile(r"(?<![A-Za-z])(?=[A-E]\\?[.、．:：)）])")
TYPE_HEAD = re.compile(r"^([ABX])型题")
HTML_TAG = re.compile(r"<[^<>]+>")


GREEK = {"alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ",
         "epsilon": "ε", "zeta": "ζ", "eta": "η", "theta": "θ",
         "kappa": "κ", "lambda": "λ", "mu": "μ", "nu": "ν", "xi": "ξ",
         "pi": "π", "rho": "ρ", "sigma": "σ", "tau": "τ", "upsilon": "υ",
         "phi": "φ", "chi": "χ", "psi": "ψ", "omega": "ω",
         "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ",
         "Xi": "Ξ", "Pi": "Π", "Sigma": "Σ", "Phi": "Φ", "Psi": "Ψ",
         "Omega": "Ω"}
GREEK_RE = re.compile(r"\\([A-Za-z]+)")


def clean_tex(s):
    # $ \gamma $-butylamino acid -> γ-butylamino acid,Exameow不渲染LaTeX
    s = s.replace("$", "")
    # 字体命令只影响排版，不能变成题干中的字母（例如 mathrmLD50）。
    s = re.sub(r"\\(?:mathrm|mathbf|mathit|text|operatorname)\s*", "", s)
    s = re.sub(r"\\[,;:!]", " ", s)  # LaTeX空白符\, \; \: \!
    s = GREEK_RE.sub(lambda m: GREEK.get(m.group(1), m.group(1)), s)
    s = s.replace("{{", "{").replace("}}", "}")
    s = re.sub(r"_\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\^\{([^}]*)\}", r"^\1", s)
    s = re.sub(r"\{([^^{}]*)\}", r"\1", s)
    s = re.sub(r"_([A-Za-z0-9])", r"\1", s)
    s = re.sub(r"([α-ωΑ-Ω])\s+-", r"\1-", s)
    s = re.sub(r"^#+\s*", "", s)  # 残留markdown标题符
    s = re.sub(r"\s*#+$", "", s)
    s = re.sub(r" {2,}", " ", s)
    return s.strip()


def clean_opt(o):
    return clean_tex(OPT_PREFIX.sub("", o))


CN_DIGIT = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
            "六": 6, "七": 7, "八": 8, "九": 9}
SEC_ORDER = {"choice": 0, "fill": 1, "define": 2, "trans": 3, "essay": 4, "discuss": 5}
SUBJ_SECS = ("define", "trans", "essay", "discuss")
TAIL_HEAD = re.compile(r"\s*[一二三四五六七八九]、\s*\S{0,12}(对译|名词解释|问答题|简答题|论述题|填空题|选择题)\s*$")
STEM_FIXUPS = {"7. 运动失": "7. 运动失调"}  # p0235左栏OCR丢"调"


def chap_num(chap):
    # 第一章..第三十四章 -> 1..34,Exameow按行首现顺序列章节,必须书序
    m = re.match(r"第(.+?)章", chap)
    if not m:
        return 999
    s = m.group(1)
    if "十" not in s:
        return CN_DIGIT.get(s, 999)
    left, _, right = s.partition("十")
    base = 10 if not left else CN_DIGIT.get(left, 0) * 10
    return base + (CN_DIGIT.get(right, 0) if right else 0)


def split_inline_questions(s):
    # "6. atropine 12. 阿曲库铵"一行多题切开,单题原样返回
    parts = Q_SPLIT_INLINE.split(s)
    if len(parts) <= 1:
        return [s]
    return [p for p in parts if Q_START.match(p)] or [s]


def source_documents(source_dir=None, corrections_path=None):
    """保留原始 OCR；只应用有扫描页依据、旧文本精确匹配的勘误。"""
    book = get_book("yaoli")
    source_dir = Path(source_dir) if source_dir is not None else book.cache
    corrections_path = Path(corrections_path) if corrections_path else book.corrections / "source.json"
    fixes = json.loads(corrections_path.read_text(encoding="utf-8")) if corrections_path.exists() else []
    for f in sorted(source_dir.glob("p*.md")):
        text = f.read_text(encoding="utf-8")
        for fix in fixes:
            if fix["page"] != f.name:
                continue
            if text.count(fix["old"]) != 1:
                raise ValueError(f"{f.name}: 勘误原文不唯一或已变化: {fix['reason']}")
            text = text.replace(fix["old"], fix["new"], 1)
        yield f, text


def build_bank(source_dir=None, corrections_path=None):
    # 两遍:先收题(章节,节,题号)->题,再从参考答案回填
    # 只认"精选习题"内的"一、选择题/二、填空题/三、对译/四、问答题",
    # 学习要点小节(一、拟胆碱药…)不再误切sec,问答题不再漏进上一题题干
    bank, cur, sec, in_ans, in_quiz, ans_key, x_mode = {}, "", "", False, False, None, False
    b_pool, b_collecting, sec_fresh = None, False, False
    question_key = None
    for f, page_text in source_documents(source_dir, corrections_path):
        for line in page_text.splitlines():
            s = line.strip()
            if "<" in s and ">" in s:  # 去OCR表格/图片html残留
                s = HTML_TAG.sub(" ", s).strip()
            if s and not re.search(r"[一-鿿A-Za-z0-9]", s):
                continue  # 纯装饰符号行(♠️/☀️/☆/☐/*****)不进题干答案
            if s.startswith("#") and "参考答案" in s:
                in_ans = True
                continue
            m = re.match(r"#{1,2}\s*(药理学模拟试题\S*)", s)
            if m:
                cur = "第四十八章" + re.sub(r"\s+", "", m.group(1))
                in_ans, in_quiz, sec, x_mode = False, False, "", False
                b_pool, b_collecting, sec_fresh = None, False, False
                continue
            m = re.match(r"#{1,2}\s*(第.+?章)\s*(.*)", s)
            if m:
                cur = re.sub(r"\s+", "", clean_tex(m.group(1) + m.group(2)))
                in_ans, in_quiz, sec, x_mode = False, False, "", False
                b_pool, b_collecting, sec_fresh = None, False, False
                continue
            if "精选习题" in s:
                in_quiz = True
                continue
            m = re.match(r"(#{1,2}\s*)?([一二三四五六七八九])、\s*(.*)", s)
            if m:
                hashes, title = m.group(1) or "", m.group(3)
                hit = next((v for kw, v in SEC_KEYWORDS if kw in title), None)
                if hit:
                    sec, in_quiz, x_mode = hit, True, False
                    b_pool, b_collecting, sec_fresh = None, False, True
                    continue
                if hashes:  # 学习要点小节(一、拟胆碱药…),离开习题区
                    sec, in_quiz = "", False
                    b_pool, b_collecting, sec_fresh = None, False, False
                    continue
                # 纯文本"一、…"正文枚举不断状态,走正常续行逻辑
            if re.match(r"#{1,2}\s*(学习要点|复习地图)", s):
                sec, in_quiz = "", False
                continue
            if not in_quiz or not sec or not cur:
                continue
            fresh = sec_fresh if s else False
            if s:
                sec_fresh = False
            if in_ans and sec == "choice":  # "1. E 2. D ..."一行多题
                pairs = re.findall(r"(\d+)\\?[.、．]\s*([A-E](?:[\s,，、]*[A-E])*)", s)
                for num, a in pairs:
                    a = re.sub(r"[\s,，、]", "", a)
                    key = (cur, sec, int(num))
                    if key in bank:
                        bank[key]["answer"] = a
                        ans_key = key
                for num, a in re.findall(r"(?<!\d)(\d+)([A-E]{1,5})\b", s):
                    # "20AD"漏点粘连,带点已收过,此处只补无点
                    key = (cur, sec, int(num))
                    if key in bank and not bank[key]["answer"]:
                        bank[key]["answer"] = a
                        ans_key = key
                mb = re.match(r"^([A-E]{1,5})\s+(?=\d)", s)
                if mb and pairs:
                    # 行首裸答案"D 2.C 3.D…",归前一题(如26章Q1)
                    key = (cur, sec, int(pairs[0][0]) - 1)
                    if int(pairs[0][0]) > 1 and key in bank and not bank[key]["answer"]:
                        bank[key]["answer"] = mb.group(1)
                        ans_key = key
                continue
            mt = TYPE_HEAD.match(s.lstrip("#").strip())
            if mt:  # A型/X型/B型题小标题,不进题干选项
                t = mt.group(1)
                if t == "X":
                    x_mode = True
                elif t == "A":
                    x_mode = False
                if t == "B":
                    x_mode = False
                    b_pool, b_collecting = [], True
                else:
                    b_pool, b_collecting = None, False
                continue
            m = Q_START.match(s.lstrip("#").strip())  # "### 7. 螺内酯"
            if m:
                sq = s.lstrip("#").strip()
                for part in split_inline_questions(sq):
                    pm = Q_START.match(part)
                    if not pm:
                        continue
                    num = int(pm.group(1))
                    body = re.sub(r"\s*[ABX]型题\s*$", "", pm.group(2).strip())
                    tm = TAIL_HEAD.search(body)
                    body = TAIL_HEAD.sub("", body)  # "…E。四、中英文药名对译"行内标题尾
                    key = (cur, sec, num)
                    if in_ans:
                        if key in bank:  # 答案无对应题则丢弃
                            bank[key]["answer"] = body
                            ans_key = key
                        elif sec in SUBJ_SECS:
                            # 题印错节(对译题跑到问答标题下),找同章同号空答案
                            alt = next((k for k in bank if k[0] == cur and
                                        k[1] in SUBJ_SECS and
                                        k[1] != sec and k[2] == num and
                                        not bank[k]["answer"]), None)
                            if alt is not None:
                                bank[alt]["answer"] = body
                                ans_key = alt
                    elif key not in bank:
                        bank[key] = {"stem": body, "options": [],
                                     "answer": "", "chapter": cur, "sec": sec,
                                     "x": x_mode, "source": f.name}
                        if sec == "choice" and b_pool:  # B型题共用选项
                            bank[key]["options"] = list(b_pool)
                            b_collecting = False
                        question_key = key
                    if tm:  # 行内标题尾:后续行切到新节
                        hit = next((v for kw, v in SEC_KEYWORDS if kw in tm.group(1)), None)
                        if hit and hit != sec:
                            sec, x_mode = hit, False
                            b_pool, b_collecting, sec_fresh = None, False, True
                continue
            if s and (bank or b_collecting):
                if re.fullmatch(r"[-－—\s]*\d{1,4}[-－—\s]*", s):
                    continue  # 页码"2023"不进题干/选项/答案
                ms = re.match(r"^[（(]([^)）]*?)[)）]$", s)
                if ms and 2 <= len(ms.group(1).strip()) <= 15 and re.fullmatch(
                        r"[一-鿿\s]+", ms.group(1).strip()):
                    continue  # 编写者署名如(李晓明 刘浩)
                if s.startswith("#"):  # 未识别的标题行不进题干答案
                    continue
                if fresh and sec in SUBJ_SECS and not re.match(
                        r"^[A-E][.、]", s):
                    # 单题小节无编号问答("请举一例…"/"答：…"),单立条目
                    keys = [k for k in bank if k[0] == cur and k[1] == sec]
                    if in_ans:
                        if keys:
                            ans_key = max(keys)
                            bank[ans_key]["answer"] += s
                    elif keys:
                        num = max(k[2] for k in keys) + 1
                    else:
                        num = 1
                    if not in_ans:
                        bank[(cur, sec, num)] = {"stem": s, "options": [],
                                                 "answer": "", "chapter": cur,
                                                 "sec": sec, "x": False, "source": f.name}
                        question_key = (cur, sec, num)
                    continue
                if not in_ans:  # 选项/题干续行
                    # 小节导语不能续接上一节的最后一题/选项。
                    if not b_collecting and (question_key is None or question_key[:2] != (cur, sec)):
                        continue
                    if s.startswith("#"):
                        continue
                    if sec == "choice" and OPT_PREFIX.match(s):
                        opts = [x for x in OPT_BOUNDARY.split(s) if x.strip()]
                        if b_pool is not None:
                            # B型题的新一组从 A 开始；上一组题目已复制各自的选项。
                            if s.startswith("A") and not b_collecting:
                                b_pool = []
                            b_collecting = True
                            b_pool += opts
                        else:
                            last = bank[question_key]
                            last["options"] += opts
                    else:
                        last = bank[question_key] if question_key else None
                        if b_collecting and b_pool and sec == "choice":
                            b_pool[-1] += s
                        elif last is not None and not last["options"]:
                            last["stem"] += s
                        elif last is not None:
                            last["options"][-1] += s  # 选项折行续接
                elif sec in SUBJ_SECS and ans_key:  # 答案续行
                    bank[ans_key]["answer"] += s
    qs = []
    for (chap, sec, num), q in sorted(
            bank.items(), key=lambda kv: (chap_num(kv[0][0]), kv[0][0],
                                           SEC_ORDER[kv[0][1]], kv[0][2])):
        chap = re.sub(r"\s+", "", chap)  # 章节名去空白归一展示
        if sec == "choice":
            labels = "".join(o.strip()[0] for o in q["options"])
            expected = "ABCDE"[:len(q["options"])]
            if labels != expected:
                raise ValueError(f"{chap} 第{num}题选项标号不连续: {labels}")
            a = re.sub(r"\s+", "", q["answer"])
            qs.append({"stem": clean_tex(f"{num}. {q['stem']}"),
                       "type": "单选题" if len(a) <= 1 and not q.get("x") else "多选题",
                       "options": [clean_opt(o) for o in q["options"]],
                       "answer": a, "chapter": chap})
        elif sec == "fill":
            qs.append({"stem": clean_tex(f"{num}. {q['stem']}"), "type": "填空题",
                       "options": [],
                       "answer": clean_tex(q["answer"].replace("，", "|")),
                       "chapter": chap})
        else:
            stem = clean_tex(f"{num}. {q['stem']}")
            qs.append({"stem": STEM_FIXUPS.get(stem, stem), "type": "简答题",
                       "options": [], "answer": clean_tex(q["answer"]),
                       "chapter": chap})
        qs[-1].update(section=sec, number=num, source=q["source"])
    return qs


def parse(book, rules):
    from ..plugins import ParseResult
    return ParseResult(build_bank(book.cache))
