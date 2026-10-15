"""Bind declared raw aliases without inventing absent or linked variables."""
import xml.etree.ElementTree as ET

import pytest

from tunerpro_exporter import UniversalXDFExporter
from tunerpro_xdf.xdf_equations import EquationError


def scalar(uid, address, equation, variables):
    return f'''<XDFCONSTANT uniqueid="{uid}"><title>Scalar {uid}</title>
      <EMBEDDEDDATA mmedaddress="{address}" mmedelementsizebits="16" />
      <MATH equation="{equation}">{variables}</MATH></XDFCONSTANT>'''


def exporter(tmp_path, definitions):
    binary = tmp_path / "fixture.bin"
    raw = bytearray(4096)
    raw[0x100:0x102] = (3200).to_bytes(2, "big")
    raw[0x102:0x104] = (1600).to_bytes(2, "big")
    raw[0x104:0x106] = (640).to_bytes(2, "big")
    binary.write_bytes(raw)
    xdf = tmp_path / "fixture.xdf"
    xdf.write_text('<XDFFORMAT version="1.70"><XDFHEADER><deftitle>Raw aliases</deftitle>'
                   '</XDFHEADER>' + definitions + '</XDFFORMAT>', encoding="utf-8")
    result = UniversalXDFExporter(str(xdf), str(binary))
    assert result.validate_bin_file() and result.parse_xdf()
    return result


def test_declared_w_alias_reads_current_scalar_raw_bytes(tmp_path):
    ex = exporter(tmp_path, scalar("0x1", "0x100", "w/160", '<VAR id="w" />') +
                  scalar("0x2", "0x102", "W/160", '<VAR id="w" />'))
    assert [ex.read_constant(item) for item in ex.elements['constants']] == [(3200, 20), (1600, 10)]
    assert ex.run_diagnostics()['decode_error_count'] == 0


def test_absent_alias_is_not_invented(tmp_path):
    ex = exporter(tmp_path, scalar("0x1", "0x100", "w/160", '<VAR id="X" />'))
    with pytest.raises(EquationError, match="Missing variable: w"):
        ex.read_constant(ex.elements['constants'][0])


def test_address_variable_is_not_bound_to_current_raw(tmp_path):
    ex = exporter(tmp_path, scalar("0x1", "0x100", "w/160",
                  '<VAR id="w" type="address" address="0x104" sizeinbits="16" />'))
    assert ex.read_constant(ex.elements['constants'][0]) == (3200, 4)


def test_recursive_link_decodes_target_raw_alias(tmp_path):
    ex = exporter(tmp_path, scalar("0x1", "0x100", "w/160", '<VAR id="w" />') +
                  scalar("0x2", "0x102", "w+X", '<VAR id="w" type="link" linkid="0x1" />'))
    assert ex.read_constant(ex.elements['constants'][1]) == (1600, 1620)


def test_per_cell_math_keeps_its_own_alias_scope(tmp_path):
    table = '''<XDFTABLE uniqueid="0x3"><title>Alias table</title>
      <XDFAXIS id="x"><indexcount>2</indexcount></XDFAXIS>
      <XDFAXIS id="y"><indexcount>1</indexcount></XDFAXIS>
      <XDFAXIS id="z"><EMBEDDEDDATA mmedaddress="0x100" mmedelementsizebits="16"
        mmedrowcount="1" mmedcolcount="2" />
        <MATH equation="w/160"><VAR id="w" /></MATH>
            <MATH row="0" col="1" equation="q/80"><VAR id="q" /></MATH>
      </XDFAXIS></XDFTABLE>'''
    ex = exporter(tmp_path, table)
    assert ex._read_table_data(ex.elements['tables'][0]) == [[20, 20]]


def test_supplied_context_binding_remains_authoritative(tmp_path):
    ex = exporter(tmp_path, scalar("0x1", "0x100", "X", '<VAR id="X" />'))
    conversion = ET.fromstring('<MATH equation="Y+w"><VAR id="Y" /><VAR id="w" /></MATH>')
    assert ex.evaluate_math("Y+w", 3200, {'y_axis_value': 3}, math_element=conversion)[0] == 3203
