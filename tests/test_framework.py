import random
import tempfile
import unittest
from unittest.mock import patch
from dataclasses import replace
from pathlib import Path

from meowcannery.catalog import get_book
from meowcannery.cli import page_selection
from meowcannery.export import HEADERS, read_xlsx, write_xlsx
from meowcannery.parsers.rule_based import parse
from meowcannery.plugins import load_plugin
from meowcannery.plugins import ParseResult
from meowcannery.pipeline import inspect_book
from meowcannery.presets import book_rules, load_preset, merge_rules
from meowcannery.quiz import generate, remap
from meowcannery.text import plain_text
from meowcannery.validation import validate_bank


class RuleTests(unittest.TestCase):
    def parse(self, *texts, preset="chapter_answers", rules=None):
        with tempfile.TemporaryDirectory() as directory:
            for i, text in enumerate(texts, 1):
                Path(directory, f"p{i:04d}.md").write_text(text, encoding="utf-8")
            book = replace(get_book("fenxi"), id="test_fixture", config="test_fixture", ocr_dir=directory,
                           chapters={}, first_page=1, last_page=len(texts), preset=preset, rules=rules or {})
            return parse(book, book_rules(book))

    def test_shared_groups_across_pages_and_letter_references(self):
        result = self.parse("""# 第一章 测试
## 习题
## 一、配伍选择题
[1~2]
A. 甲 B. 乙 C. 丙 D. 丁 E. A、B、C、D 都可以
请判断下列情况
1. 第一题
2. 第二题 [3~4]
A. 一 B. 二
""", """C. 三 D. 四 E. 五
3. 第三题
4. 第四题
## 参考答案
## 一、配伍选择题
[1~2] AE [3~4] BC
""")
        self.assertEqual(result.issues, [])
        validate_bank(result.questions)
        self.assertEqual([q["answer"] for q in result.questions], list("AEBC"))
        self.assertEqual(result.questions[0]["options"][-1], "A、B、C、D 都可以")
        self.assertEqual(result.questions[2]["options"], list("一二三四五"))
        self.assertIn("请判断", result.questions[0]["stem"])
        self.assertNotIn("3~4", result.questions[1]["stem"])

    def test_section_numbers_do_not_collide_and_end_stops_theory(self):
        result = self.parse("""# 第一章 测试
## 一、单选题
1. 问题
A. 甲 B. 乙
## 二、计算题
1. 计算内容
## 参考答案
## 一、单选题
1. B
## 二、计算题
1. 解：结果
## 知识地图
理论内容不属于答案
""")
        self.assertEqual(result.issues, [])
        self.assertEqual([q["answer"] for q in result.questions], ["B", "解：结果"])

    def test_configured_shared_intro_preserves_continuation_and_resets(self):
        result = self.parse("""# 第一章 测试
## 一、配伍选择题
[1~2]
A. 无水碳酸钠 B. 邻苯二甲酸
氢钾
标定下列物质应选用基准物质是
1. NaOH（）。
""", """2. HCl（）。
[3~3]
A. 甲 B. 乙
3. 下一组（）。
## 参考答案
## 一、配伍选择题
[1~2] BA [3~3] A
""", preset="analytical_guide")
        self.assertEqual(result.issues, [])
        for q in result.questions[:2]:
            self.assertEqual(q["options"], ["无水碳酸钠", "邻苯二甲酸 氢钾"])
            self.assertIn("标定下列物质应选用基准物质是", q["stem"])
        self.assertNotIn("标定下列", result.questions[2]["stem"])
        self.assertEqual(result.questions[2]["options"], ["甲", "乙"])

    def test_grouped_answers_for_multiple_blanks_require_review(self):
        result = self.parse("""# 第一章 测试
## 一、多选题
1. 第一类（），第二类（）。
A. 甲 B. 乙 C. 丙 D. 丁
2. 常规多选（）。
A. 甲 B. 乙 C. 丙 D. 丁
## 参考答案
## 一、多选题
1. AB, CD 2. A, C
""")
        self.assertIn("分组答案", result.questions[0]["review_reasons"][0])
        self.assertNotIn("review_reasons", result.questions[1])
        self.assertEqual(result.questions[1]["answer"], "AC")

    def test_inline_answers_are_a_working_preset(self):
        result = self.parse("""# 第一章 示例
## 一、单选题
1. 问题
A. 甲 B. 乙
答案：B
解析：解释
2. 另一个问题
A. 丙 B. 丁
参考答案：A
""", preset="inline_answers")
        self.assertEqual(result.issues, [])
        self.assertEqual([q["answer"] for q in result.questions], ["B", "A"])
        self.assertEqual(result.questions[0]["explanation"], "解释")

    def test_numeric_stem_and_display_math_question(self):
        result = self.parse(r"""# 第一章 测试
## 一、简答题
1.1000 的有效位数是多少？
$$ 2.pH=pK_a(\quad). $$
## 参考答案
## 一、简答题
1. 答案一
2. 答案二
""")
        self.assertEqual(len(result.questions), 2)
        self.assertEqual(result.questions[1]["answer"], "答案二")

    def test_range_length_mismatch_and_orphan_answers_are_visible(self):
        result = self.parse("""# 第一章 测试
## 一、配伍选择题
[1~2]
A. 甲 B. 乙
1. 问题
## 参考答案
## 一、配伍选择题
[1~2] A
3. B
""")
        self.assertTrue(any("数量不符" in i["reason"] for i in result.issues))
        self.assertTrue(any("没有对应题目" in i["reason"] for i in result.issues))

    def test_table_numbers_and_decimal_continuation_do_not_start_questions(self):
        result = self.parse("""# 第一章 测试
## 一、计算题
1. 根据表格计算
<table><tr><td>1.5</td><td>0.362</td></tr><tr><td>2.5</td><td>0.673</td></tr></table>
2.1000 的有效位数是多少？
## 参考答案
## 一、计算题
1. 解：当数值为
5.7时，对应值为4.3。
2. 解：见定义。
""")
        self.assertEqual(result.issues, [])
        self.assertEqual(len(result.questions), 2)
        self.assertIn("1.5 │ 0.362", result.questions[0]["stem"])
        self.assertIn("5.7时", result.questions[0]["answer"])

    def test_math_range_judgment_and_inline_numeric_fill_answers(self):
        result = self.parse(r"""# 第一章 测试
## 一、配伍选择题
A. 甲 B. 乙
1. 甲题
2. 乙题
## 二、判断题（正确打√，错误打×）
1. 陈述一
2. 陈述二
## 三、填空题
1. 数值一
2. 数值二
## 参考答案
## 一、配伍选择题
$ [1\sim2] $ AB
## 二、判断题
$$ 1.\surd\quad2.\times $$
## 三、填空题
1. 91.87。2. 0.2～0.8。
""")
        self.assertEqual(result.issues, [])
        self.assertEqual([q["answer"] for q in result.questions], ["A", "B", "√", "×", "91.87", "0.2～0.8。"])

    def test_letter_enumeration_in_stem_does_not_create_options(self):
        result = self.parse("""# 第一章 测试
## 一、单选题
1. A、B、C、D 四种组分的顺序是？
A. D, B, C, A
B. A, C, D, B
## 参考答案
## 一、单选题
1. A
""")
        self.assertEqual(result.questions[0]["options"], ["D, B, C, A", "A, C, D, B"])

    def test_duplicate_question_and_answer_are_reported(self):
        result = self.parse("""# 第一章 测试
## 一、问答题
1. 原问题
1. 重复问题
## 参考答案
## 一、问答题
1. 原答案
1. 重复答案
""")
        self.assertEqual(len(result.issues), 2)
        self.assertEqual(result.questions[0]["answer"], "原答案")

    def test_medical_continuous_numbering(self):
        result = self.parse("""# 第一章 测试
## 一、选择题
A型题
1. 单选
A. 甲 B. 乙
B型题
A. 丙 B. 丁
2. 配伍
X型题
3. 多选
A. 戊 B. 己
## 参考答案
## 一、选择题
1. A 2. B 3. AB
""", preset="medical_abx")
        self.assertEqual(result.issues, [])
        self.assertEqual([q["answer"] for q in result.questions], ["A", "B", "AB"])
        self.assertEqual([q["type"] for q in result.questions], ["单选题", "单选题", "多选题"])

    def test_html_answer_cells_remain_separate(self):
        result = self.parse("""# 第一章 测试
## 一、多选题
1. 问题
A. 甲 B. 乙
2. 问题二
A. 丙 B. 丁
## 参考答案
## 一、多选题
<table><tr><td>1. A, B</td><td>2. A B</td></tr></table>
""")
        self.assertEqual([q["answer"] for q in result.questions], ["AB", "AB"])


class FrameworkTests(unittest.TestCase):
    def test_preset_override_does_not_mutate_parent(self):
        parent = load_preset("chapter_answers")
        overridden = merge_rules(parent, {"sections": {"案例": "discuss"}})
        self.assertIn("案例", overridden["sections"])
        self.assertNotIn("案例", parent["sections"])

    def test_local_plugin_and_unknown_plugin(self):
        self.assertTrue(callable(load_plugin("example")))
        with self.assertRaises(ValueError):
            load_plugin("missing_plugin")

    def test_page_selection(self):
        self.assertEqual(page_selection("3-5,4,9"), [3, 4, 5, 9])
        with self.assertRaises(ValueError):
            page_selection("5-2")

    def test_math_preserves_fraction_charge_and_inequality(self):
        self.assertEqual(plain_text(r"$\mathrm{Fe}^{3+} + \frac{a+b}{c} \leqslant 10^{-2}$"), "Fe³⁺ + (a+b)/(c) ≤ 10⁻²")
        self.assertEqual(plain_text(r"$\frac{1}{\sqrt{n}}$"), "(1)/(√(n))")
        self.assertIn(r"\unknown", plain_text(r"$\unknown{x}$"))

    def test_excel_roundtrip_preserves_literal_formula_and_leading_zeros(self):
        with tempfile.TemporaryDirectory() as directory:
            q = dict(stem="=a+b", type="简答题", options=[], answer="0012", chapter="测试", subject="分析化学")
            path = Path(directory) / "bank.xlsx"
            write_xlsx([q], path)
            restored = read_xlsx(path)
            self.assertEqual(restored[0]["stem"], "=a+b")
            self.assertEqual(restored[0]["answer"], "0012")
            from openpyxl import load_workbook
            wb = load_workbook(path)
            self.assertEqual(wb.active["A2"].data_type, "s")
            self.assertEqual([c.value for c in wb.active[1]], HEADERS)
            wb.close()

    def test_failed_export_does_not_overwrite_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bank.xlsx"
            path.write_bytes(b"original")
            with self.assertRaises(ValueError):
                write_xlsx([], path)
            self.assertEqual(path.read_bytes(), b"original")

    def test_shuffle_preserves_correct_option_content(self):
        options, answer = remap(["A. 甲", "B. 乙", "C. 丙"], "AC", random.Random(5))
        self.assertEqual({options[ord(c)-65] for c in answer}, {"甲", "丙"})

    def test_insufficient_questions_fail_without_partial_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "paper"
            bank = [dict(stem="题目", type="单选题", options=["甲", "乙"], answer="A", chapter="第一章")]
            with self.assertRaises(ValueError):
                generate(bank, output, single=2)
            self.assertFalse(output.with_suffix(".txt").exists())

    def test_ambiguous_parser_result_is_excluded_even_if_fields_are_valid(self):
        q = dict(stem="1. 问题", type="简答题", options=[], answer="答案", chapter="第一章", section="essay", number=1)
        result = ParseResult([q], [dict(chapter="第一章", section="essay", number=1, source="p0001.md", reason="答案题号重复：1")])
        book = replace(get_book("fenxi"), id="test_fixture", config="test_fixture")
        with patch("meowcannery.pipeline.load_plugin", return_value=lambda *_: result), patch("meowcannery.pipeline.book_rules", return_value={}):
            _, accepted, review = inspect_book(book, require_complete=False)
        self.assertEqual(accepted, [])
        self.assertEqual(review[0]["reasons"], ["答案题号重复：1"])

    def test_long_option_is_rejected_before_excel_can_truncate_it(self):
        q = dict(stem="问题", type="单选题", options=["长"*32768, "短"], answer="A", chapter="第一章")
        with self.assertRaisesRegex(ValueError, "选项超过 Excel"):
            validate_bank([q])


if __name__ == "__main__":
    unittest.main()
