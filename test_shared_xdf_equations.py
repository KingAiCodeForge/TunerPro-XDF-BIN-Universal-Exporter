"""Safety and compatibility tests for the standalone numerical XDF evaluator."""

import ast
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from tunerpro_xdf.xdf_equations import EquationError, evaluate_equation, inverse_affine
from tunerpro_xdf import xdf_equations


@pytest.mark.parametrize("equation, variables, expected", [
    ("X*0.75-40", {"X": 128}, 56),
    ("X/128", {"x": 256}, 2),
    ("-0.375*X-60.0", {"X": 128}, -108),
    ("1.000000 * X + 0.000000", {"X": 7}, 7),
    ("(0.351563 * X) + 0.000000", {"X": 16}, 5.625008),
    ("X/2.56", {"X": 256}, 100),
    ("(x+B)*c", {"X": 10, "b": 4, "C": 0.5}, 7),
    ("X1000+X", {"X1000": 3, "X": 4}, 7),
    ("X/B/E+A+Y", {"X": 12, "B": 2, "E": 3, "A": 4, "Y": 5}, 11),
    ("2+3*4-10/2", {}, 9),
    ("(+X % 4) + 0x10", {"x": 7}, 19),
    ("2**3**2", {}, 512),
    ("-2**2", {}, -4),
    ("2**-2", {}, 0.25),
    ("(X >> 2) & 0xF | 0x10", {"X": 44.0}, 27),
    ("(X << 2) ^ 3", {"X": 4}, 19),
    ("~X", {"X": 1}, -2),
    ("2^3", {}, 1),
    ("sqrt(16)+ABS(-2)+int(3.9)+float(2)", {}, 11),
    ("POW(2;((X+128)/32))", {"X": 0}, 16),
    ("pow(2,3)+log(8;2)+log10(100)", {}, 13),
    ("SIN(PI/2)+cos(0)+tan(0)", {"PI": math.pi}, 2),
    ("exp(0)+floor(2.9)+ceil(2.1)+round(2.5)", {}, 8),
    ("max(1;4;2)+min(3,2)", {}, 6),
    ("X&#013;&#010; *0.75-40&#xA;", {"X": 128}, 56),
    ("\n X\t/\r\n128 ", {"X": 256}, 2),
])
def test_evaluation(equation, variables, expected):
    assert evaluate_equation(equation, variables) == pytest.approx(expected)


@pytest.mark.parametrize("operator, expected", [("<", 1), ("<=", 1), (">", 0), (">=", 0), ("==", 0), ("!=", 1)])
def test_comparisons(operator, expected):
    result = evaluate_equation(f"X {operator} 4", {"X": 3})
    assert type(result) is int and result == expected


@pytest.mark.parametrize("value, expected", [(0, 5), (1, 3), (2, 4)])
def test_nested_conditionals_are_lazy(value, expected):
    equation = "2+IF(X>0; if(X==1; 1; 2); if(1; 3; 1/0))"
    assert evaluate_equation(equation, {"X": value}) == expected
    assert evaluate_equation("if(0; sqrt(-1); if(1; 9; B))", {}) == 9
    assert evaluate_equation("if(1; 4; 2**1000000000)", {}) == 4


def test_xml_parser_and_literal_entities_agree():
    equation = "X&#013;&#010; / 128"
    parsed = ET.fromstring(f'<MATH equation="{equation}"/>').get("equation")
    assert evaluate_equation(parsed, {"X": 256}) == evaluate_equation(equation, {"X": 256}) == 2


@pytest.mark.parametrize("equation", ["", " ", "null", "(null)", " NULL ", "(NuLl)", "&#013;&#010;"])
def test_identity_literals(equation):
    assert evaluate_equation(equation, {"x": 37}) == 37
    assert inverse_affine(equation, 37.4, {}) == 37
    with pytest.raises(EquationError, match="Missing variable"):
        evaluate_equation(equation, {})


@pytest.mark.parametrize("name", ["X", "A", "B", "C", "E", "Y", "Z", "PI", "X1000"])
def test_variables_are_never_invented(name):
    with pytest.raises(EquationError, match="Missing variable"):
        evaluate_equation(f"{name}+1", {})


@pytest.mark.parametrize("equation", [
    "__import__('os').system('echo unsafe')", "open('payload', 'w')", "eval('1')",
    "exec('pass')", "compile('1','','eval')", "X.__class__", "(1).__class__",
    "getattr(X,'real')", "math.sqrt(4)", "X[0]", "[X for X in Y]", "(X for X in Y)",
    "{1:2}", "{1,2}", "[1,2]", "(lambda: 1)()", "f'{X}'", "b'X'", "'X'",
    "X; 2", "1,2", "X if X else 0", "X and 1", "not X", "True", "False", "None",
    "1j", "sqrt(X=4)", "sqrt(*X)", "sqrt(**X)", "unknown(1)", "1 # comment",
    "if(1;2;unknown(3))", "if(1;2;X[0])", "1 < X < 3", "X//2", "X:=2",
    "X&#95;", "X&#000000000000000000000000000013;", "X&bogus;", "X + \N{FULLWIDTH DIGIT ONE}",
    "if(1;2)", "if(1;2;3;4)", "pow(2;3;5)", "sqrt()", "abs(1;2)",
    "X +", "(X", "X)", "*2", "/128",
])
def test_rejects_unsupported_syntax(equation):
    with pytest.raises(EquationError):
        evaluate_equation(equation, {"X": 1})


@pytest.mark.parametrize("equation", [
    "1/0", "1%0", "sqrt(-1)", "log(0)", "log(4;1)", "acos(2)",
    "0**-1", "pow(-1;.5)", "(-1)**0.5", "exp(1000)", "1e309", "1e308*1e308",
    "X+1", "X+1.0", "X*2", "X**2", "int(1e309)",
])
def test_domain_and_nonfinite_failures(equation):
    with pytest.raises(EquationError):
        evaluate_equation(equation, {"X": float("inf")})
    if not equation.startswith("X"):
        with pytest.raises(EquationError):
            evaluate_equation(equation, {})


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), 1 << 1024, "2", None, True, complex(1, 0)])
def test_rejects_invalid_variable_and_inverse_values(value):
    with pytest.raises(EquationError):
        evaluate_equation("X", {"X": value})
    with pytest.raises(EquationError):
        inverse_affine("X", value, {})


@pytest.mark.parametrize("equation", [
    "2**1000000000", "pow(2;1000000000)", "2**(2**20)", "(2**512)**512",
    "pow(.5;-1000000000)", "pow(1;1e308)", "(2**600)*(2**600)",
    "1<<1000000000", "1>>1000000000", "1<<-1", "1<<1024", "1<<1.5", "3.5 & 1",
    "("*65 + "1" + ")"*65, "-"*65 + "1", "1+"*300 + "1", "9"*257,
    " "*4096 + "1", "0x" + "F"*256 + "+1", "0x" + "F"*256 + "*2",
])
def test_rejects_resource_bombs(equation):
    with pytest.raises(EquationError):
        evaluate_equation(equation, {})


def test_numeric_limits_allow_normal_bounded_operations():
    assert evaluate_equation("1<<1023", {}) == 1 << 1023
    assert evaluate_equation("2**1023", {}) == 2**1023
    assert evaluate_equation("(2**500)*(2**500)", {}) == 2**1000
    assert evaluate_equation("pow(0;1024)", {}) == 0


@pytest.mark.parametrize("equation", ["X+1", "X*2", "X<<1", "X**2"])
def test_intermediate_integer_limits(equation):
    with pytest.raises(EquationError):
        evaluate_equation(equation, {"X": (1 << 1024) - 1})


def test_resource_checks_precede_expensive_operations(monkeypatch):
    def forbidden(*args):
        raise AssertionError("Operation reached before resource check")

    monkeypatch.setattr(xdf_equations.operator, "pow", forbidden)
    monkeypatch.setitem(xdf_equations._BINARY, ast.Mult, forbidden)
    monkeypatch.setitem(xdf_equations._BINARY, ast.LShift, forbidden)
    for equation in ("pow(2;1e9)", "2**1e9", "X*X", "1<<1000000"):
        with pytest.raises(EquationError):
            evaluate_equation(equation, {"X": 1 << 600})


def test_case_alias_conflicts_and_non_numeric_protocols():
    assert evaluate_equation("X", {"X": 1, "x": 1}) == 1
    with pytest.raises(EquationError):
        evaluate_equation("X", {"X": 1, "x": 2})

    class UntrustedInt(int):
        def __add__(self, other):
            raise AssertionError("Must not invoke user numeric methods")

    with pytest.raises(EquationError):
        evaluate_equation("X+1", {"X": UntrustedInt(1)})


@pytest.mark.parametrize("equation, variables", [
    (None, {}), ([], {}), (1, {}), ("X", None), ("X", []),
    ("X", {1: 1}), ("X", {"__builtins__": 1}),
])
def test_invalid_api_inputs_raise_equation_error(equation, variables):
    with pytest.raises(EquationError):
        evaluate_equation(equation, variables)
    with pytest.raises(EquationError):
        inverse_affine(equation, 1, variables)


@pytest.mark.parametrize("equation, value, variables, expected", [
    ("X*0.75-40", 56, {}, 128),
    ("X/128", 2, {}, 256),
    ("-0.375*x-60.0", -108, {}, 128),
    ("(X+B)*C", 7, {"b": 4, "C": 0.5}, 10),
    ("2*(3-X)/4", -2, {}, 7),
    ("X+X+3", 23, {}, 10),
    ("X-X+3*X", 18, {}, 6),
    ("pow(2;B)*X+sqrt(C)", 20, {"B": 2, "C": 16}, 4),
    ("if(B;2*X;3*X)", 12, {"B": 1}, 6),
    ("X", 2.5, {}, 2),
    ("X", 3.5, {}, 4),
    ("X", -2.5, {}, -2),
    ("X", 12, {"X": 999}, 12),
    ("X", (1 << 60) + 1, {}, (1 << 60) + 1),
    ("X-2", (1 << 60) + 1, {}, (1 << 60) + 3),
    ("X/3", (1 << 60) + 1, {}, 3 * ((1 << 60) + 1)),
])
def test_affine_inverse(equation, value, variables, expected):
    result = inverse_affine(equation, value, variables)
    assert type(result) is int and result == expected


@pytest.mark.parametrize("equation", [
    "X*X", "X**2", "X**1", "pow(X;2)", "1/X", "X/X", "sqrt(X)", "abs(X)",
    "int(X)", "floor(X)", "round(X)", "X%3", "X>>1", "X<<1", "X&255", "X^2",
    "X|0", "~X", "X>0", "min(X;10)", "max(X;10)", "sin(X)", "if(X;X;X)",
    "if(X<10;X;X*2)", "if(X==0;0;if(X==1;1;9))", "X+X*(X-1)*(X-2)",
    "X+X*(X-1)*(X+1)", "X+(X-X)*X", "X+(X/1e300/1e300)*X", "X/(X-X+1)",
    "X-X", "X*0", "3", "X*B", "X+B", "X/0", "X*1e308*1e308",
])
def test_inverse_refuses_unproven_or_degenerate_forms(equation):
    with pytest.raises(EquationError):
        inverse_affine(equation, 12, {})


def test_inverse_rejects_zero_linked_coefficient_and_overflow():
    with pytest.raises(EquationError):
        inverse_affine("X*B", 12, {"B": 0})
    with pytest.raises(EquationError):
        inverse_affine("X/1e300", 1e300, {})
    with pytest.raises(EquationError, match="rational size limit"):
        inverse_affine("X/1e300/1e300/1e300/1e300/1e300", 1, {})


def test_source_never_executes_equation_code():
    source = Path(xdf_equations.__file__)
    tree = ast.parse(source.read_text(encoding="utf-8"))
    calls = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert not calls.intersection({"eval", "exec", "compile", "__import__"})
