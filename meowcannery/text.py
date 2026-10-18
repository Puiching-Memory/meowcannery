"""将 OCR 排版转换为 Exameow 可显示的纯文本，保留数学语义。"""
import html
import re
from html.parser import HTMLParser

SYMBOLS = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε",
    "varepsilon": "ε", "theta": "θ", "lambda": "λ", "mu": "μ", "nu": "ν",
    "pi": "π", "rho": "ρ", "sigma": "σ", "tau": "τ", "phi": "φ", "varphi": "φ",
    "chi": "χ", "psi": "ψ", "omega": "ω", "Delta": "Δ", "Sigma": "Σ", "Phi": "Φ",
    "Omega": "Ω", "Gamma": "Γ", "Lambda": "Λ", "Theta": "Θ",
    "times": "×", "cdot": "·", "cdots": "…", "ldots": "…", "dots": "…",
    "pm": "±", "mp": "∓", "sim": "～", "approx": "≈", "simeq": "≃",
    "equiv": "≡", "neq": "≠", "ne": "≠", "leq": "≤", "le": "≤",
    "geq": "≥", "ge": "≥", "infty": "∞", "propto": "∝", "partial": "∂",
    "rightarrow": "→", "to": "→", "longrightarrow": "⟶", "leftarrow": "←",
    "leftrightarrow": "↔", "rightleftharpoons": "⇌", "leftrightharpoons": "⇋",
    "circ": "°", "degree": "°", "prime": "′", "ell": "ℓ", "sum": "Σ",
    "int": "∫", "nabla": "∇", "vert": "|", "mid": "|", "langle": "〈", "rangle": "〉",
    "quad": " ", "qquad": " ", "enspace": " ", "space": " ", "qquad": " ",
    "log": "log", "ln": "ln", "lg": "lg", "sin": "sin", "cos": "cos", "tan": "tan",
    "exp": "exp", "max": "max", "min": "min", "lim": "lim", "checkmark": "√",
    "div": "÷", "leqslant": "≤", "geqslant": "≥", "because": "∵", "therefore": "∴",
    "bullet": "·", "Rightarrow": "⇒", "Leftarrow": "⇐", "Leftrightarrow": "⇔",
    "downarrow": "↓", "uparrow": "↑", "longleftrightarrow": "⟷", "Longrightarrow": "⟹",
    "triangle": "△", "surd": "√",
}
SUP = str.maketrans("0123456789+-=()ni", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ")
SUB = str.maketrans("0123456789+-=()aehijklmnoprstuvx", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ")


def _group(text, position):
    while position < len(text) and text[position].isspace():
        position += 1
    if position >= len(text):
        return "", position
    if text[position] != "{":
        match = re.match(r"\\[a-zA-Z]+|.", text[position:])
        return match[0], position + len(match[0])
    start, depth = position + 1, 1
    position += 1
    while position < len(text) and depth:
        depth += (text[position] == "{") - (text[position] == "}")
        position += 1
    return text[start:position-1] if not depth else text[start:], position


def _math(text):
    out, i = [], 0
    while i < len(text):
        if text[i] in "^_":
            symbol = text[i]
            value, i = _group(text, i + 1)
            value = _math(value).strip()
            mapping = SUP if symbol == "^" else SUB
            out.append(value.translate(mapping) if value and all(ord(c) in mapping for c in value)
                       else f"{symbol}({value})")
            continue
        if text[i] == "{":
            value, i = _group(text, i)
            out.append(_math(value))
            continue
        match = re.match(r"\\([A-Za-z]+)", text[i:])
        if match:
            command = match[1]
            i += len(match[0])
            if command in ("frac", "dfrac", "tfrac"):
                a, i = _group(text, i)
                b, i = _group(text, i)
                out.append(f"({_math(a).strip()})/({_math(b).strip()})")
            elif command in ("mathrm", "mathbf", "boldsymbol", "mathit", "text", "textrm", "operatorname", "mathsf", "ce", "mbox", "underline"):
                value, i = _group(text, i)
                out.append(_math(value))
            elif command in ("sqrt", "overline", "bar", "vec", "hat", "tilde"):
                value, i = _group(text, i)
                value = _math(value)
                marks = {"sqrt": "√", "bar": "̄", "overline": "̄", "vec": "⃗", "hat": "̂", "tilde": "̃"}
                out.append(f"√({value})" if command == "sqrt" else value + marks[command])
            elif command == "textcircled":
                value, i = _group(text, i)
                out.append(chr(0x245f + int(value)) if value.isdigit() and 1 <= int(value) <= 20 else f"({value})")
            elif command in ("left", "right", "displaystyle", "textstyle", "limits", "nolimits",
                             "big", "Big", "bigg", "Bigg", "bigl", "bigr", "Bigl", "Bigr"):
                pass
            elif command in ("hspace", "vspace", "kern", "mkern"):
                _, i = _group(text, i)
                out.append(" ")
            elif command in SYMBOLS:
                out.append(SYMBOLS[command])
            else:
                out.append("\\" + command)  # 未知命令保留，交由质量检查报告。
            continue
        if text[i] == "\\" and i + 1 < len(text):
            i += 1
            out.append(" " if text[i] in ",;:! " else text[i])
        elif text[i] not in "$}":
            out.append(text[i])
        i += 1
    return "".join(out)


def plain_text(text):
    text = html.unescape(text).replace("**", "")
    text = text.translate(str.maketrans({"✓": "√", "✔": "√", "✗": "×", "✘": "×"}))
    text = re.sub(r"\\begin\{(?:aligned|align\*?|gathered|array|cases)\}(?:\{[lcr| ]+\})?", "", text)
    text = re.sub(r"\\end\{(?:aligned|align\*?|gathered|array|cases)\}", "", text)
    text = text.replace(r"\\", "\n").replace("&", " ")
    text = text.replace(r"\(", "").replace(r"\)", "").replace(r"\[", "").replace(r"\]", "")
    return re.sub(r"[ \t]+", " ", _math(text)).strip()


class _TableText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.parts.append("\n│ ")
        elif tag == "br":
            self.parts.append("\n")
        if tag == "img":
            self.parts.append(" [原页图片] ")

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self.parts.append(" │ ")
        elif tag in ("tr", "table", "div", "p"):
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)


def source_lines(text):
    # 表格先保留单元格边界，避免 1.A / 2.B 在清理标签后粘连。
    def replace(match):
        parser = _TableText()
        parser.feed(match[0])
        return "".join(parser.parts)
    text = re.sub(r"<(table|div|p)\b[^>]*>.*?</\1>|<img\b[^>]*>", replace, text, flags=re.S)
    return text.splitlines()
