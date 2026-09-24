"""Bounded numerical XDF equations, without executing Python expressions.

Names are case insensitive; all variables (including PI/E) come from the caller.
Function arguments accept TunerPro semicolons or legacy commas. ``^`` is XOR,
as documented at https://tunerpro.net/WebHelp/source/genconv.htm; ``**`` is the
legacy exporter's power spelling. Empty/null equations mean identity; implicit
X prefixes are left to the caller. Unsupported syntax fails closed.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from fractions import Fraction
from functools import lru_cache
import io
import keyword
import math
import operator
import re
import tokenize


__all__ = ["EquationError", "evaluate_equation", "inverse_affine"]

_MAX_LENGTH = 4096
_MAX_TOKENS = 512
_MAX_DEPTH = 64
_MAX_LITERAL_LENGTH = 256
_MAX_INTEGER_BITS = 1024
_MAX_INTEGER = (1 << _MAX_INTEGER_BITS) - 1
_MAX_POWER_EXPONENT = 1024
_MAX_SHIFT = 1024
_MAX_FRACTION_BITS = 4096
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]*\Z")
_XML_NUMBER = re.compile(r"&#(?:[xX][0-9a-fA-F]+|[0-9]+);")
_KEYWORDS = {name.lower() for name in keyword.kwlist} - {"if"}
_OPERATORS = {
    "+", "-", "*", "/", "%", "**", "<<", ">>", "&", "|", "^", "~",
    "<", "<=", ">", ">=", "==", "!=", "(", ")", ",", ";",
}
_BINARY = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Mod: operator.mod,
    ast.BitAnd: operator.and_, ast.BitOr: operator.or_, ast.BitXor: operator.xor,
    ast.LShift: operator.lshift, ast.RShift: operator.rshift,
}
_COMPARE = {
    ast.Lt: operator.lt, ast.LtE: operator.le, ast.Gt: operator.gt,
    ast.GtE: operator.ge, ast.Eq: operator.eq, ast.NotEq: operator.ne,
}
_FUNCTIONS = {
    "abs": (abs, 1, 1), "int": (int, 1, 1), "float": (float, 1, 1),
    "sqrt": (math.sqrt, 1, 1), "exp": (math.exp, 1, 1),
    "log": (math.log, 1, 2), "log10": (math.log10, 1, 1),
    "sin": (math.sin, 1, 1), "cos": (math.cos, 1, 1),
    "tan": (math.tan, 1, 1), "asin": (math.asin, 1, 1),
    "acos": (math.acos, 1, 1), "atan": (math.atan, 1, 1),
    "floor": (math.floor, 1, 1), "ceil": (math.ceil, 1, 1),
    "round": (round, 1, 1), "min": (min, 2, 16), "max": (max, 2, 16),
}


class EquationError(ValueError):
    """An equation is unsupported, undefined, or exceeds a resource limit."""


def _checked(value):
    # Reject objects with executable numeric protocols, not just non-numbers.
    if type(value) is int:
        if value.bit_length() > _MAX_INTEGER_BITS:
            raise EquationError("Integer size limit exceeded")
    elif type(value) is float:
        if not math.isfinite(value):
            raise EquationError("Non-finite number")
    else:
        raise EquationError("Only built-in int and float values are supported")
    return value


def _integer(value):
    if type(value) is float and not value.is_integer():
        raise EquationError("Bitwise operands must be integers")
    return _checked(int(value))


def _power(base, exponent):
    if abs(exponent) > _MAX_POWER_EXPONENT:
        raise EquationError("Power exponent limit exceeded")
    if base < 0 and type(exponent) is float and not exponent.is_integer():
        raise EquationError("Power requires a real-valued result")
    if base and exponent and exponent != 1:
        # Estimate size before exponentiation, including reciprocal powers.
        if math.log2(abs(base)) * exponent >= _MAX_INTEGER_BITS:
            raise EquationError("Power result size limit exceeded")
    return _checked(operator.pow(base, exponent))


def _binary(kind, left, right):
    if kind is ast.Pow:
        return _power(left, right)
    if kind in (ast.BitAnd, ast.BitOr, ast.BitXor, ast.LShift, ast.RShift):
        left, right = _integer(left), _integer(right)
    if kind in (ast.LShift, ast.RShift):
        if not 0 <= right <= _MAX_SHIFT:
            raise EquationError("Shift count limit exceeded")
        if kind is ast.LShift and left and left.bit_length() + right > _MAX_INTEGER_BITS:
            raise EquationError("Shift result size limit exceeded")
    if kind is ast.Mult and type(left) is int and type(right) is int:
        if right and abs(left) > _MAX_INTEGER // abs(right):
            raise EquationError("Multiplication result size limit exceeded")
    return _checked(_BINARY[kind](left, right))


def _xml_whitespace(match):
    text = match.group()[2:-1]
    # Only XML whitespace entities are normalized; other entities are not code.
    if len(text) > 10:
        raise EquationError("Unsupported XML numeric entity")
    number = int(text[1:], 16) if text[:1].lower() == "x" else int(text)
    if number not in (9, 10, 13, 32):
        raise EquationError("Only XML whitespace entities are supported")
    return " "


def _normalize(equation):
    if type(equation) is not str:
        raise EquationError("Equation must be a string")
    if len(equation) > _MAX_LENGTH:
        raise EquationError("Equation length limit exceeded")
    if not equation.isascii():
        raise EquationError("Only ASCII equation syntax is supported")
    equation = " ".join(_XML_NUMBER.sub(_xml_whitespace, equation).split())
    if equation.lower() in ("", "null", "(null)"):
        return "x"
    output = []
    depth = 0
    for token in tokenize.generate_tokens(io.StringIO(equation).readline):
        kind, value = token.type, token.string
        if kind in (tokenize.ENDMARKER, tokenize.NEWLINE, tokenize.NL):
            continue
        if len(output) >= _MAX_TOKENS:
            raise EquationError("Equation token limit exceeded")
        if kind == tokenize.NAME:
            if not _NAME.fullmatch(value) or value.lower() in _KEYWORDS:
                raise EquationError("Unsupported name or keyword")
            value = "_if" if value.lower() == "if" else value.lower()
        elif kind == tokenize.NUMBER:
            if len(value) > _MAX_LITERAL_LENGTH or "_" in value:
                raise EquationError("Unsupported or oversized numeric literal")
        elif kind == tokenize.OP and value in _OPERATORS:
            if value == "(":
                depth += 1
                if depth > _MAX_DEPTH:
                    raise EquationError("Equation nesting limit exceeded")
            elif value == ")":
                depth -= 1
                if depth < 0:
                    raise EquationError("Unmatched parentheses")
            elif value == ";":
                value = ","
        else:
            raise EquationError("Unsupported equation token")
        output.append(value)
    return " ".join(output)


@lru_cache(maxsize=128)
def _parse(equation):
    # ast.parse produces data only. No generated AST is compiled or executed.
    root = ast.parse(_normalize(equation), mode="eval").body
    pending = [(root, 1)]
    count = 0
    while pending:
        node, depth = pending.pop()
        count += 1
        if depth > _MAX_DEPTH or count > _MAX_TOKENS:
            raise EquationError("Equation AST size/depth limit exceeded")
        if isinstance(node, ast.Constant):
            _checked(node.value)
            children = []
        elif isinstance(node, ast.Name) and _NAME.fullmatch(node.id):
            children = []
        elif isinstance(node, ast.BinOp) and type(node.op) in (*_BINARY, ast.Pow):
            children = [node.left, node.right]
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub, ast.Invert)):
            children = [node.operand]
        elif isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in _COMPARE:
            children = [node.left, node.comparators[0]]
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
            name = node.func.id
            if name == "_if":
                low = high = 3
            elif name == "pow":
                low = high = 2
            elif name in _FUNCTIONS:
                _, low, high = _FUNCTIONS[name]
            else:
                raise EquationError(f"Unsupported function: {name}")
            if not low <= len(node.args) <= high:
                raise EquationError(f"Invalid argument count for {name}")
            children = node.args
        else:
            raise EquationError(f"Unsupported syntax: {type(node).__name__}")
        pending.extend((child, depth + 1) for child in children)
    return root


def _variables(variables):
    if not isinstance(variables, Mapping) or len(variables) > _MAX_TOKENS:
        raise EquationError("Variables must be a size-bounded mapping")
    result = {}
    for name, value in variables.items():
        if type(name) is not str or len(name) > _MAX_LENGTH or not _NAME.fullmatch(name):
            raise EquationError("Invalid variable name")
        name, value = name.lower(), _checked(value)
        if name in result and result[name] != value:
            raise EquationError(f"Conflicting case-insensitive variable: {name}")
        result[name] = value
    return result


def _evaluate(node, variables):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id not in variables:
            raise EquationError(f"Missing variable: {node.id}")
        return variables[node.id]
    if isinstance(node, ast.BinOp):
        return _binary(type(node.op), _evaluate(node.left, variables), _evaluate(node.right, variables))
    if isinstance(node, ast.UnaryOp):
        value = _evaluate(node.operand, variables)
        if isinstance(node.op, ast.Invert):
            return _checked(~_integer(value))
        return _checked(-value if isinstance(node.op, ast.USub) else value)
    if isinstance(node, ast.Compare):
        return int(_COMPARE[type(node.ops[0])](
            _evaluate(node.left, variables), _evaluate(node.comparators[0], variables)
        ))
    name = node.func.id
    if name == "_if":
        branch = node.args[1] if _evaluate(node.args[0], variables) else node.args[2]
        return _evaluate(branch, variables)
    args = [_evaluate(arg, variables) for arg in node.args]
    if name == "pow":
        return _power(*args)
    return _checked(_FUNCTIONS[name][0](*args))


def _depends_on_x(node):
    return any(isinstance(child, ast.Name) and child.id == "x" for child in ast.walk(node))


def _fraction_binary(kind, left, right):
    # Predict numerator/denominator growth before Fraction multiplies or runs gcd.
    ln, ld = left.numerator.bit_length(), left.denominator.bit_length()
    rn, rd = right.numerator.bit_length(), right.denominator.bit_length()
    if kind in (ast.Add, ast.Sub):
        numerator, denominator = max(ln + rd, rn + ld) + 1, ld + rd
    elif kind is ast.Mult:
        numerator, denominator = ln + rn, ld + rd
    else:
        if right == 0:
            raise EquationError("Division by zero in affine expression")
        numerator, denominator = ln + rd, ld + rn
    if max(numerator, denominator) > _MAX_FRACTION_BITS:
        raise EquationError("Affine rational size limit exceeded")
    result = _BINARY[kind](left, right)
    if abs(result) > _MAX_INTEGER:
        raise EquationError("Affine numeric size limit exceeded")
    return result


def _affine(node, variables):
    if not _depends_on_x(node):
        return Fraction(0), Fraction(_evaluate(node, variables))
    if isinstance(node, ast.Name):
        return Fraction(1), Fraction(0)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        a, b = _affine(node.operand, variables)
        return (-a, -b) if isinstance(node.op, ast.USub) else (a, b)
    if isinstance(node, ast.Call) and node.func.id == "_if" and not _depends_on_x(node.args[0]):
        branch = node.args[1] if _evaluate(node.args[0], variables) else node.args[2]
        return _affine(branch, variables)
    if isinstance(node, ast.BinOp):
        kind = type(node.op)
        if kind in (ast.Add, ast.Sub):
            a, b = _affine(node.left, variables)
            c, d = _affine(node.right, variables)
            return _fraction_binary(kind, a, c), _fraction_binary(kind, b, d)
        if kind is ast.Mult:
            # Track syntactic dependence, even if a coefficient cancels/underflows.
            if _depends_on_x(node.left) and _depends_on_x(node.right):
                raise EquationError("Product of X-dependent expressions is not proven affine")
            dependent, constant = (node.left, node.right) if _depends_on_x(node.left) else (node.right, node.left)
            a, b = _affine(dependent, variables)
            scale = Fraction(_evaluate(constant, variables))
            return _fraction_binary(kind, a, scale), _fraction_binary(kind, b, scale)
        if kind is ast.Div and not _depends_on_x(node.right):
            a, b = _affine(node.left, variables)
            divisor = Fraction(_evaluate(node.right, variables))
            return _fraction_binary(kind, a, divisor), _fraction_binary(kind, b, divisor)
    raise EquationError("Expression is not proven affine in X")


_FAILURES = (ArithmeticError, SyntaxError, tokenize.TokenError, RecursionError, MemoryError, TypeError, ValueError)


def evaluate_equation(equation: str, variables: Mapping[str, int | float]) -> int | float:
    """Evaluate supported numerical syntax, raising EquationError on any failure.

    ``if(condition; yes; no)`` evaluates only its selected branch, but syntax in
    every branch must be supported. Bitwise operands must be integral (3.0 is
    accepted; 3.5 is not truncated). Empty/null forms mean X. Comparisons return
    0 or 1. Parsing is bounded
    to 4096 characters, 512 tokens/nodes, and depth 64; integers to 1024 bits;
    exponents to magnitude 1024; shifts to counts 0..1024.
    """
    try:
        return _checked(_evaluate(_parse(equation), _variables(variables)))
    except EquationError:
        raise
    except _FAILURES as exc:
        raise EquationError(f"Invalid equation: {exc}") from exc


def inverse_affine(equation: str, real_value: int | float, variables: Mapping[str, int | float]) -> int:
    """Invert an AST-proven a*X+b, rounding ties to even using Python round.

    X is symbolic, not required in variables. Other variables are held constant.
    Only affine arithmetic and conditionals with X-independent conditions are
    proven; no sampling, nonlinear cancellation, or implicit inverse is used.
    Rational coefficients preserve integer precision; their intermediate
    numerators and denominators are bounded to 4096 bits before arithmetic.
    """
    try:
        real_value = _checked(real_value)
        a, b = _affine(_parse(equation), _variables(variables))
        if a == 0:
            raise EquationError("Affine coefficient of X must be nonzero")
        delta = _fraction_binary(ast.Sub, Fraction(real_value), b)
        raw = _fraction_binary(ast.Div, delta, a)
        return _checked(round(raw))
    except EquationError:
        raise
    except _FAILURES as exc:
        raise EquationError(f"Invalid affine inverse: {exc}") from exc
