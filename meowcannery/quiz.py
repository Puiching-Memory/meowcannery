"""从新生成的题库确定性抽题并重排选项。"""
import random
import re
from pathlib import Path

from .validation import validate_bank

OPTION_PREFIX = re.compile(r"^\s*[A-H][.、．:：)）]\s*")


def remap(options, answer, rng=None):
    rng = rng or random.Random()
    if not answer or any(c not in "ABCDEFGH"[:len(options)] for c in answer) or len(set(answer)) != len(answer):
        raise ValueError("选项重排前答案无效。")
    order = list(range(len(options)))
    rng.shuffle(order)
    remapped = "".join(sorted(chr(65 + order.index(ord(c) - 65)) for c in answer))
    return [OPTION_PREFIX.sub("", options[i]) for i in order], remapped


def generate(bank, output, *, single=10, multi=0, fill=0, short=0, seed=7, chapter=""):
    validate_bank(bank)
    requested = dict(单选题=single, 多选题=multi, 填空题=fill, 简答题=short)
    if any(count < 0 for count in requested.values()) or not sum(requested.values()):
        raise ValueError("抽题数量不能为负数，且至少选择一道题。")
    rng, picked = random.Random(seed), []
    filtered = [q for q in bank if chapter in q["chapter"]]
    for kind, count in requested.items():
        pool = [q for q in filtered if q["type"] == kind]
        if count > len(pool):
            raise ValueError(f"{kind}可用 {len(pool)} 题，少于请求的 {count} 题。请调整数量或章节。")
        picked.extend(rng.sample(pool, count))
    rng.shuffle(picked)
    paper, key = [f"模拟卷 · 共 {len(picked)} 题", ""], [f"参考答案 · seed={seed}", ""]
    for i, q in enumerate(picked, 1):
        paper.append(f"{i}. [{q['type']}] {q['stem']}")
        answer = q["answer"]
        if q["options"]:
            options, answer = remap(q["options"], answer, rng)
            paper.extend(f"   {chr(65+j)}. {option}" for j, option in enumerate(options))
        key.extend([f"{i}. {answer}", f"   来源：{q['chapter']} / {q['stem'][:60]}", ""])
        paper.append("")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    for suffix, lines in ((".txt", paper), ("_key.txt", key)):
        Path(str(output) + suffix).write_text("\n".join(lines), encoding="utf-8")
    print(f"已生成 {len(picked)} 题：{output}.txt / {output}_key.txt")
    return picked
