"""本地分析化学 OCR 的集成回归；无书籍资料时自动跳过。"""
import unittest

from meowcannery.catalog import get_book
from meowcannery.pipeline import inspect_book, required_pages
from meowcannery.validation import validate_bank

BOOK = get_book("fenxi")


@unittest.skipUnless(all((BOOK.cache / f"p{p:04d}.md").is_file() for p in required_pages(BOOK)), "需要本地分析化学 OCR 缓存")
class AnalyticalRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result, cls.accepted, cls.review = inspect_book(BOOK)

    def question(self, chapter, section, number):
        return next(q for q in self.result.questions if q["chapter"].startswith(chapter+" ") and q["section"] == section and q["number"] == number)

    def test_complete_page_coverage_and_answer_mapping(self):
        self.assertEqual(len(self.result.questions), 899)
        self.assertEqual(self.result.issues, [])
        self.assertTrue(all(q["answer"] for q in self.result.questions))
        validate_bank(self.accepted)

    def test_restored_question_numbers_and_nuclear_notation(self):
        self.assertIn("主要部件", self.question("第十章", "essay", 5)["stem"])
        self.assertIn("双嘧达莫", self.question("第十章", "calculate", 5)["stem"])
        self.assertIn("¹²₆C", self.question("第十四章", "shared", 3)["stem"])
        self.assertEqual(self.question("第十一章", "judge", 12)["answer"], "×")

    def test_scanned_graph_pool_and_carbonyl_do_not_contaminate_neighbors(self):
        q = self.question("第八章", "shared", 9)
        self.assertEqual(len(q["options"]), 5)
        self.assertIn("ΔE/ΔV", q["options"][2])
        self.assertNotIn("曲线", self.question("第八章", "shared", 8)["stem"])
        self.assertIn("C(=O)", self.question("第十章", "single", 8)["options"][2])
        self.assertNotIn("原页图片", str(self.question("第十章", "single", 9)))

    def test_review_questions_never_enter_the_import_bank(self):
        ids = {(q["chapter"], q["section"], q["number"]) for q in self.accepted}
        self.assertTrue(self.review)
        for entry in self.review:
            q = entry["question"]
            self.assertNotIn((q["chapter"], q["section"], q["number"]), ids)
