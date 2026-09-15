"""可复制的书籍插件示例：先复用预设解析，再添加本书特有校验。"""
from meowcannery.parsers.rule_based import parse as parse_rules


def parse(book, rules):
    result = parse_rules(book, rules)
    # 可在此处理本书独有的标题或编号；不要无依据猜写缺失答案。
    return result
