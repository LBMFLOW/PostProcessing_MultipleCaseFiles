"""Small curve-label formula evaluator."""

from __future__ import annotations


DEFAULT_CURVE_LABEL_FORMULA = "('curve_label'-{'|','.trn'}+\"_\"+'parameter')"


def format_curve_label(
    formula: str,
    curve_label: str,
    parameter: str,
    fallback: str,
) -> str:
    """Format a curve label from a constrained expression.

    Supported syntax:
    - variables: `curve_label`, `parameter`, or their quoted forms
    - string literals: `"_"` or `'literal'`
    - concatenation: `+`
    - substring removal from a term: `term-{'a','b'}`
    """

    expression = _unwrap_parentheses(formula.strip() or DEFAULT_CURVE_LABEL_FORMULA)
    if _uses_curve_label(expression) and not curve_label.strip():
        return fallback

    try:
        parts = [_evaluate_term(term, curve_label, parameter) for term in _split_top_level(expression)]
    except ValueError:
        return fallback

    label = "".join(parts).strip()
    return label or fallback


def _uses_curve_label(expression: str) -> bool:
    return "curve_label" in expression


def _unwrap_parentheses(expression: str) -> str:
    while expression.startswith("(") and expression.endswith(")"):
        candidate = expression[1:-1].strip()
        if not candidate:
            return expression
        expression = candidate
    return expression


def _split_top_level(expression: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    quote: str | None = None
    brace_depth = 0

    for character in expression:
        if quote is not None:
            current.append(character)
            if character == quote:
                quote = None
            continue

        if character in {"'", '"'}:
            quote = character
            current.append(character)
            continue
        if character == "{":
            brace_depth += 1
            current.append(character)
            continue
        if character == "}":
            brace_depth -= 1
            if brace_depth < 0:
                raise ValueError("Unbalanced braces in label formula.")
            current.append(character)
            continue
        if character == "+" and brace_depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue
        current.append(character)

    if quote is not None or brace_depth != 0:
        raise ValueError("Unbalanced label formula.")

    parts.append("".join(current).strip())
    return [part for part in parts if part]


def _evaluate_term(term: str, curve_label: str, parameter: str) -> str:
    base, removals = _split_removal(term)
    value = _term_value(base, curve_label, parameter)
    for removal in removals:
        value = value.replace(removal, "")
    return value


def _split_removal(term: str) -> tuple[str, list[str]]:
    quote: str | None = None
    brace_depth = 0
    for index, character in enumerate(term):
        if quote is not None:
            if character == quote:
                quote = None
            continue
        if character in {"'", '"'}:
            quote = character
            continue
        if character == "{":
            brace_depth += 1
            continue
        if character == "}":
            brace_depth -= 1
            continue
        if character == "-" and brace_depth == 0:
            return term[:index].strip(), _parse_removal_set(term[index + 1 :].strip())
    return term.strip(), []


def _parse_removal_set(removal_set: str) -> list[str]:
    if not removal_set.startswith("{") or not removal_set.endswith("}"):
        raise ValueError("Label removals must be written as {'text','text'}.")

    inner = removal_set[1:-1].strip()
    if not inner:
        return []

    removals: list[str] = []
    for part in _split_comma_separated(inner):
        removals.append(_strip_quotes(part.strip()))
    return removals


def _split_comma_separated(value: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    quote: str | None = None

    for character in value:
        if quote is not None:
            current.append(character)
            if character == quote:
                quote = None
            continue
        if character in {"'", '"'}:
            quote = character
            current.append(character)
            continue
        if character == ",":
            parts.append("".join(current))
            current = []
            continue
        current.append(character)

    if quote is not None:
        raise ValueError("Unbalanced removal set.")
    parts.append("".join(current))
    return parts


def _term_value(term: str, curve_label: str, parameter: str) -> str:
    normalized = _strip_quotes(term.strip())
    if normalized == "curve_label":
        return curve_label.strip()
    if normalized == "parameter":
        return parameter.strip()
    return normalized


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
