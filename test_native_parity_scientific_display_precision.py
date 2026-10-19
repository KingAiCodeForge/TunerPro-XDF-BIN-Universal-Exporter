"""Native display precision tests; synthetic numbers, not an ECU/GUI session."""
import math
import pytest
from tunerpro_native_export_parity import parse_args, parse_display_number, display_matches

def test_negative_exponent_scales_actual_display_quantum():
    n=parse_display_number("1.20e-3")
    assert n.decimals==5
    ok,delta,tolerance=display_matches(n,0.001204,0)
    assert ok and tolerance<0.00001
    bad,delta2,_=display_matches(n,0.004,0)
    assert not bad and delta2>0.002

def test_integer_scientific_notation_is_not_half_unit_absolute():
    n=parse_display_number("1e-4")
    assert n.decimals==4
    assert display_matches(n,0.00014,0)[0]
    assert not display_matches(n,0.1,0)[0]

def test_positive_exponent_has_coarser_display_quantum():
    n=parse_display_number("1.2e+3")
    assert n.decimals==-2
    assert display_matches(n,1240,0)[0]
    assert not display_matches(n,1275,0)[0]

def test_plain_integer_and_fixed_point_unchanged():
    assert parse_display_number("123").decimals==0
    assert parse_display_number("1.230").decimals==3
    assert display_matches(parse_display_number("1.230"),1.23049,0)[0]
    assert not display_matches(parse_display_number("1.230"),1.231,0)[0]

def test_small_scientific_does_not_receive_fixed_slack():
    n=parse_display_number("1.00e-14")
    good,delta,tolerance=display_matches(n,1.001e-14,0)
    assert good
    assert tolerance<1e-12
    assert not display_matches(n,1.05e-13,0)[0]

@pytest.mark.parametrize("value",[-1,math.nan,math.inf,-math.inf])
def test_bad_absolute_tolerance_refused(value):
    with pytest.raises(ValueError,match="tolerance"):
        display_matches(parse_display_number("1e-3"),0.001,value)

@pytest.mark.parametrize("text",["1e309","-1e999","1e-1000","nan","inf","abc"])
def test_unrepresentable_native_display_refused(text):
    with pytest.raises(ValueError):
        parse_display_number(text)

def test_nonfinite_candidate_is_mismatch_not_success():
    n=parse_display_number("1.00")
    assert not display_matches(n,float("nan"),0)[0]
    assert not display_matches(n,float("inf"),0)[0]


def test_subnormal_display_quantum_outside_float_range_is_refused():
    for text in ("5e-324", "4e-324", "1.00e-323", "-5e-324"):
        with pytest.raises(ValueError, match="display quantum"):
            parse_display_number(text)


def test_display_precision_at_float_ulp_resolution_is_refused():
    with pytest.raises(ValueError, match="finer than binary float resolution"):
        parse_display_number("1e-323")
    n = parse_display_number("1e-322")
    ok, delta, tolerance = display_matches(n, n.value, 0)
    assert ok and tolerance > 0 and math.isfinite(tolerance)


def test_large_exponent_half_unit_boundaries_allow_float_representation_slack():
    n = parse_display_number("1.0e308")
    quantum = 1e307
    lower = n.value - 0.5 * quantum
    upper = n.value + 0.5 * quantum
    assert display_matches(n, lower, 0)[0]
    assert display_matches(n, upper, 0)[0]
    # One representational step outside the mathematical boundary is still
    # inside the deliberate ULP allowance. A clearly larger excursion is not.
    assert display_matches(n, math.nextafter(lower, -math.inf), 0)[0]
    assert display_matches(n, math.nextafter(upper, math.inf), 0)[0]
    step = max(math.ulp(lower), math.ulp(upper), math.ulp(n.value))
    assert not display_matches(n, lower - 8 * step, 0)[0]
    assert not display_matches(n, upper + 8 * step, 0)[0]


def test_extreme_finite_positive_exponent_is_supported_without_overflow():
    n = parse_display_number("1e308")
    ok, delta, tolerance = display_matches(n, 1e308, 0)
    assert ok
    assert math.isfinite(tolerance)
    assert tolerance == 5e307 or tolerance > 5e307


def test_cli_default_does_not_override_native_scientific_precision():
    args = parse_args(["native.txt", "export.json"])
    assert args.absolute_tolerance == 0.0
    n = parse_display_number("1.00e-14")
    assert display_matches(n, 1.001e-14, args.absolute_tolerance)[0]
    assert not display_matches(n, 1.05e-13, args.absolute_tolerance)[0]


def test_explicit_absolute_tolerance_remains_opt_in():
    args = parse_args(["native.txt", "export.json", "--absolute-tolerance", "1e-9"])
    assert args.absolute_tolerance == 1e-9
    n = parse_display_number("1.00e-14")
    assert display_matches(n, 1.05e-13, args.absolute_tolerance)[0]
