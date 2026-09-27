"""A tiny evaluator for the formulas this project writes into Excel.

Used by the verification test to prove that the *formulas in the generated
file* — not just the values the engine computed — reproduce the stored
`PayrollLine` numbers. That is the difference between "we wrote a spreadsheet"
and "we wrote a spreadsheet that still works when someone edits a cell".

It handles exactly the grammar the generator emits: `=`, a leading `+`, cell
references, decimal literals, `%`, the four operators, parentheses, and the two
aggregate forms `SUM(range)` and `SUBTOTAL(9,range)`.
"""

from __future__ import annotations

import re
from decimal import Decimal, DivisionByZero, InvalidOperation

CELL_RE = re.compile(r"\$?([A-Z]{1,3})\$?(\d+)")
RANGE_RE = re.compile(r"\$?([A-Z]{1,3})\$?(\d+):\$?([A-Z]{1,3})\$?(\d+)")
SUM_RE = re.compile(r"SUM\(([^)]*)\)", re.IGNORECASE)
SUBTOTAL_RE = re.compile(r"SUBTOTAL\(\s*9\s*,([^)]*)\)", re.IGNORECASE)
SAFE_RE = re.compile(r"^[0-9+\-*/(). ]+$")


class FormulaError(ValueError):
    """The formula used something this evaluator deliberately does not support."""


def column_index(letters: str) -> int:
    index = 0
    for char in letters:
        index = index * 26 + (ord(char) - ord("A") + 1)
    return index


MAX_DEPTH = 32


def _literal(value: Decimal) -> str:
    """Plain decimal text: `Decimal('0E-26')` must not reach the parser as `0E-26`."""
    return format(value, "f")


def evaluate(formula: str, cells) -> Decimal:
    """Evaluate one formula against a `(row, column_letter) -> value` accessor."""
    return _Evaluator(cells).evaluate(formula)


class _Evaluator:
    """Resolves a formula, following references into other formula cells.

    A calculated column like `O` is built from `H`, `J` and `L`, which are
    themselves formulas — so reading a referenced cell has to evaluate it rather
    than treat the formula text as zero. Results are memoised per cell, and the
    recursion is depth-capped so a circular reference fails loudly instead of
    hanging.
    """

    def __init__(self, cells):
        self.cells = cells
        self.cache: dict[tuple[int, str], Decimal] = {}

    def evaluate(self, formula: str, depth: int = 0) -> Decimal:
        expression = formula.strip()
        if expression.startswith("="):
            expression = expression[1:]
        expression = expression.lstrip("+")

        expression = self._expand_ranges(expression, depth)
        expression = self._substitute_cells(expression, depth)
        expression = _expand_percent(expression)

        if not SAFE_RE.match(expression):
            raise FormulaError(f"unsupported formula after substitution: {expression!r}")

        try:
            # Only digits, operators and parentheses remain, and `Decimal` keeps
            # the arithmetic exact rather than drifting through binary floats.
            return _eval_arithmetic(expression)
        except (DivisionByZero, InvalidOperation, ZeroDivisionError):
            return Decimal(0)

    def _expand_ranges(self, expression: str, depth: int) -> str:
        def total(match: re.Match[str]) -> str:
            return f"({self._sum_range(match.group(1), depth)})"

        expression = SUBTOTAL_RE.sub(total, expression)
        return SUM_RE.sub(total, expression)

    def _sum_range(self, body: str, depth: int) -> str:
        body = body.strip()
        span = RANGE_RE.fullmatch(body)
        if span is None:
            # `SUM(F202-AG202)` — a plain expression inside SUM().
            return self._substitute_cells(body, depth)

        start_col, start_row, end_col, end_row = span.groups()
        if column_index(start_col) != column_index(end_col):
            raise FormulaError(f"multi-column range not supported: {body!r}")

        total = Decimal(0)
        for row in range(int(start_row), int(end_row) + 1):
            total += self.value_of(row, start_col, depth)
        return _literal(total)

    def _substitute_cells(self, expression: str, depth: int) -> str:
        def replace(match: re.Match[str]) -> str:
            return f"({_literal(self.value_of(int(match.group(2)), match.group(1), depth))})"

        return CELL_RE.sub(replace, expression)

    def value_of(self, row: int, column: str, depth: int = 0) -> Decimal:
        if depth > MAX_DEPTH:
            raise FormulaError(f"formula nesting too deep at {column}{row} (circular?)")

        key = (row, column)
        if key in self.cache:
            return self.cache[key]

        value = self.cells(row, column)
        if value is None or value == "":
            result = Decimal(0)
        elif isinstance(value, Decimal):
            result = value
        elif isinstance(value, int | float):
            result = Decimal(str(value))
        elif isinstance(value, str) and value.startswith("="):
            result = self.evaluate(value, depth + 1)
        else:
            try:
                result = Decimal(str(value))
            except InvalidOperation:
                result = Decimal(0)

        self.cache[key] = result
        return result


def _expand_percent(expression: str) -> str:
    """`11%` -> `(11/100)`."""
    return re.sub(r"(\d+(?:\.\d+)?)%", r"(\1/100)", expression)


def _eval_arithmetic(expression: str) -> Decimal:
    """Evaluate a pure-arithmetic expression with Decimal semantics."""
    tokens = re.findall(r"\d+\.\d+|\d+|[+\-*/()]", expression)
    if not tokens:
        return Decimal(0)
    parser = _Parser(tokens)
    result = parser.parse_expression()
    if parser.position != len(tokens):
        raise FormulaError(f"trailing tokens in {expression!r}")
    return result


class _Parser:
    """Recursive-descent parser: expression -> term -> factor."""

    def __init__(self, tokens: list[str]):
        self.tokens = tokens
        self.position = 0

    def peek(self) -> str | None:
        return self.tokens[self.position] if self.position < len(self.tokens) else None

    def take(self) -> str:
        token = self.tokens[self.position]
        self.position += 1
        return token

    def parse_expression(self) -> Decimal:
        value = self.parse_term()
        while self.peek() in {"+", "-"}:
            operator = self.take()
            right = self.parse_term()
            value = value + right if operator == "+" else value - right
        return value

    def parse_term(self) -> Decimal:
        value = self.parse_factor()
        while self.peek() in {"*", "/"}:
            operator = self.take()
            right = self.parse_factor()
            if operator == "*":
                value = value * right
            else:
                if right == 0:
                    raise DivisionByZero
                value = value / right
        return value

    def parse_factor(self) -> Decimal:
        token = self.peek()
        if token == "+":
            self.take()
            return self.parse_factor()
        if token == "-":
            self.take()
            return -self.parse_factor()
        if token == "(":
            self.take()
            value = self.parse_expression()
            if self.peek() != ")":
                raise FormulaError("unbalanced parentheses")
            self.take()
            return value
        if token is None:
            raise FormulaError("unexpected end of formula")
        return Decimal(self.take())
