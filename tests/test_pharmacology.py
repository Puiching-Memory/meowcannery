import json
import tempfile
import unittest
from pathlib import Path

from meowcannery.parsers import pharmacology as y
from meowcannery.catalog import get_book
from meowcannery.pipeline import inspect_book
from meowcannery.validation import validate_bank
from meowcannery.export import write_xlsx


class ParserRegressionTests(unittest.TestCase):
    def parse(self, *pages):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for i, text in enumerate(pages, 1):
                (root / f"p{i:04d}.md").write_text(text, encoding="utf-8")
            fixes = root / "fixes.json"
            fixes.write_text("[]", encoding="utf-8")
            return y.build_bank(root, fixes)

    def test_shared_options_switch_groups_across_pages(self):
        qs = self.parse("""# 第一章测试
## 精选习题
## 一、选择题
B型题
A. 一 B. 二 C. 三 D. 四 E. 五
1. 第一题
2. 第二题
A．甲 B．乙 C．丙
""", """D．丁 E．戊
3. 第三题
4. 第四题
X型题
5. 第五题
A. 甲 B. 乙 C. 丙 D. 丁 E. 戊
## 参考答案
## 一、选择题
1. A 2. E 3. B 4. D 5. A, C, E
""")
        self.assertEqual([q["options"] for q in qs[:2]], [list("一二三四五")] * 2)
        self.assertEqual([q["options"] for q in qs[2:]], [list("甲乙丙丁戊")] * 3)
        self.assertEqual(qs[4]["answer"], "ACE")
        self.assertEqual(qs[4]["type"], "多选题")

    def test_abbreviations_are_not_option_markers(self):
        qs = self.parse("""# 第一章测试
## 一、选择题
1. 测试
A. 增强GABA)作用 B. 阻断NMDA）受体 C. NE、5-HT D. 甲 E. 乙
## 参考答案
## 一、选择题
1. A
""")
        self.assertEqual(qs[0]["options"], ["增强GABA)作用", "阻断NMDA）受体", "NE、5-HT", "甲", "乙"])

    def test_answer_separators_and_html_cells(self):
        qs = self.parse("""# 第一章测试
## 一、选择题
X型题
1. 第一题
A. 甲 B. 乙 C. 丙 D. 丁 E. 戊
2. 第二题
A. 甲 B. 乙 C. 丙 D. 丁 E. 戊
## 参考答案
## 一、选择题
<table><tr><td>1. A，C、E</td><td>2. B C, D, E</td></tr></table>
""")
        self.assertEqual([q["answer"] for q in qs], ["ACE", "BCDE"])

    def test_section_intro_does_not_pollute_previous_option(self):
        qs = self.parse("""# 第一章测试
## 一、选择题
1. 第一题
A. 甲 B. 乙 C. 丙 D. 丁 E. 戊
## 二、填空题
下图为示意图，请回答：
1. 测试___。
## 参考答案
## 一、选择题
1. A
## 二、填空题
1. 答案
""")
        self.assertEqual(qs[0]["options"][-1], "戊")

    def test_short_and_long_answers_have_separate_numbers(self):
        qs = self.parse("""# 药理学模拟试题一
## 三、简答题
1. 简答题干
## 四、论述题
1. 论述题干
## 参考答案
## 三、简答题
1. 简答答案
## 四、论述题
1. 论述答案
""")
        self.assertEqual([(q["stem"], q["answer"]) for q in qs],
                         [("1. 简答题干", "简答答案"), ("1. 论述题干", "论述答案")])

    def test_invalid_answer_does_not_overwrite_workbook(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bank.xlsx"
            path.write_bytes(b"original")
            q = dict(stem="1. 问题", chapter="测试", type="多选题", options=["甲", "乙"], answer="ACC")
            with self.assertRaises(ValueError):
                write_xlsx([q], path)
            self.assertEqual(path.read_bytes(), b"original")


@unittest.skipUnless(get_book("yaoli").cache.exists(), "需要本地药理学 OCR 缓存")
class RealBankRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qs = inspect_book(get_book("yaoli"))[0].questions

    def question(self, chapter, number, section="choice"):
        return next(q for q in self.qs if q["chapter"] == chapter and q["number"] == number and q["section"] == section)

    def test_complete_bank_is_valid(self):
        validate_bank(self.qs)
        self.assertEqual(len(self.qs), 2165)
        choices = [q for q in self.qs if q["section"] == "choice"]
        self.assertEqual(len(choices), 1450)
        self.assertTrue(all(len(q["options"]) in (4, 5) for q in choices))

    def test_reported_choice_pools(self):
        q = self.question("第三章药物效应动力学及其影响因素", 36)
        self.assertEqual(q["options"], ["治疗作用", "不良反应", "副作用", "毒性反应", "耐受性"])
        q = self.question("第三十四章作用于血液系统的药物", 21)
        self.assertEqual(q["options"][-1], "维生素K")
        self.assertEqual(q["answer"], "E")

    def test_scan_omissions_and_corrected_answers(self):
        q = self.question("第三十八章β-内酰胺类抗生素", 65)
        self.assertEqual(q["answer"], "ABCDE")
        q = self.question("第四十二章抗真菌药", 41)
        self.assertEqual(q["options"][-2:], ["酮康唑", "两性霉素 B"])
        for number, expected in [(51, "ABC"), (54, "ACD"), (58, "BCE"), (60, "ABD")]:
            self.assertEqual(self.question("第四十四章抗寄生虫药", number)["answer"], expected)
        self.assertEqual(self.question("第四十三章抗病毒药", 19)["answer"], "ABE")
        q = self.question("第四十八章药理学模拟试题一", 38)
        self.assertEqual(q["options"], ["阿米卡星", "青霉素 G", "庆大霉素", "两性霉素 B", "四环素"])

    def test_mock_exam_answers_do_not_overwrite_each_other(self):
        q = self.question("第四十八章药理学模拟试题二", 1, "essay")
        self.assertIn("支气管平滑肌松弛药", q["answer"])
        self.assertNotIn("受体名称", q["answer"])
        q = self.question("第四十八章药理学模拟试题二", 1, "discuss")
        self.assertIn("受体名称", q["answer"])


if __name__ == "__main__":
    unittest.main()
