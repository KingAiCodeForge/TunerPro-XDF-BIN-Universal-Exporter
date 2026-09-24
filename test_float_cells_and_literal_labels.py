"""Float (mmedtypeflags 0x10000) cells and TunerPro typed-label semantics."""

from pathlib import Path
import os
import struct
import sys
import xml.etree.ElementTree as ET

import pytest


REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

_platform = sys.platform
try:
    sys.platform = "pytest"
    from tunerpro_exporter import UniversalXDFExporter
finally:
    sys.platform = _platform

def _axis(aid, count, labels=(), math="X", emb=None, embedinfo=None):
    emb = emb or 'mmedelementsizebits="8" mmedmajorstridebits="0" mmedminorstridebits="0"'
    info = f'<embedinfo type="{embedinfo}" />' if embedinfo else ""
    labs = "".join(f'<LABEL index="{i}" value="{v}" />' for i, v in enumerate(labels))
    return (f'<XDFAXIS id="{aid}" uniqueid="0x0"><EMBEDDEDDATA {emb} />'
            f"<indexcount>{count}</indexcount>{info}{labs}"
            f'<MATH equation="{math}"><VAR id="X" /></MATH></XDFAXIS>')


def _table(uid, title, zemb, xaxis, zmath="X"):
    return (f'<XDFTABLE uniqueid="{uid}" flags="0x0"><title>{title}</title>'
            f"{xaxis}{_axis('y', 1, ['-'])}"
            f'<XDFAXIS id="z"><EMBEDDEDDATA {zemb} />'
            f'<MATH equation="{zmath}"><VAR id="X" /></MATH></XDFAXIS></XDFTABLE>')


def _fixture(tmp_path):
    data = bytearray(256)
    struct.pack_into(">4f", data, 0x00, 1.5, 2.25, -3.0, 100.0)
    struct.pack_into("<4f", data, 0x10, 1.5, 2.25, -3.0, 100.0)
    data[0x20:0x24] = bytes((1, 2, 3, 4))
    for i, (x, y) in enumerate(((10, 0.5), (20, 0.75), (30, 1.0), (40, 1.25))):
        struct.pack_into(">ff", data, 0x30 + 8 * i, x, y)
    struct.pack_into(">f", data, 0x60, 0.125)
    f32 = ('mmedtypeflags="{f}" mmedaddress="{a}" mmedelementsizebits="32" '
           'mmedrowcount="1" mmedcolcount="4" mmedmajorstridebits="{s}" '
           'mmedminorstridebits="{s}"')
    lab4 = _axis("x", 4, [1, 2, 3, 4])
    body = "".join((
        _table("0x101", "float BE", f32.format(f="0x10000", a="0x0", s=0), lab4),
        _table("0x102", "float LE", f32.format(f="0x10002", a="0x10", s=0), lab4),
        _table("0x103", "int bits", f32.format(f="0x00", a="0x0", s=0), lab4),
        _table("0x104", "interleaved curve", f32.format(f="0x10000", a="0x34", s=64),
               _axis("x", 4, emb=('mmedtypeflags="0x10000" mmedaddress="0x30" '
                                  'mmedelementsizebits="32" mmedcolcount="4" '
                                  'mmedmajorstridebits="64" mmedminorstridebits="0"'),
                     embedinfo="1")),
        _table("0x105", "typed labels with math",
               'mmedaddress="0x20" mmedelementsizebits="8" mmedrowcount="1" '
               'mmedcolcount="4" mmedmajorstridebits="0" mmedminorstridebits="0"',
               _axis("x", 4, [0, 10, 20, 30], math="0.75*X-48")),
        '<XDFCONSTANT uniqueid="0x201"><title>float scalar</title>'
        '<EMBEDDEDDATA mmedtypeflags="0x10000" mmedaddress="0x60" '
        'mmedelementsizebits="32" mmedmajorstridebits="0" mmedminorstridebits="0" />'
        '<MATH equation="X*2"><VAR id="X" /></MATH></XDFCONSTANT>',
        '<XDFCONSTANT uniqueid="0x202"><title>bad float width</title>'
        '<EMBEDDEDDATA mmedtypeflags="0x10000" mmedaddress="0x60" '
        'mmedelementsizebits="16" mmedmajorstridebits="0" mmedminorstridebits="0" />'
        '<MATH equation="X"><VAR id="X" /></MATH></XDFCONSTANT>',
    ))
    xdf = tmp_path / "float_probe.xdf"
    xdf.write_text('<XDFFORMAT version="1.70"><XDFHEADER><deftitle>float probe</deftitle>'
                   '<BASEOFFSET offset="0" subtract="0" /></XDFHEADER>'
                   f"{body}</XDFFORMAT>", encoding="ascii")
    binary = tmp_path / "float_probe.bin"
    binary.write_bytes(bytes(data))
    exporter = UniversalXDFExporter(str(xdf), str(binary))
    assert exporter.validate_bin_file()
    assert exporter.parse_xdf()
    return exporter


def _by_title(items, title):
    return next(item for item in items if item["title"] == title)


def test_float_cells_decode_big_and_little_endian(tmp_path):
    exporter = _fixture(tmp_path)
    tables = exporter.elements["tables"]
    expected = [[1.5, 2.25, -3.0, 100.0]]
    assert exporter._read_table_data(_by_title(tables, "float BE")) == expected
    assert exporter._read_table_data(_by_title(tables, "float LE")) == expected


def test_float_bits_without_flag_stay_integers(tmp_path):
    exporter = _fixture(tmp_path)
    data = exporter._read_table_data(_by_title(exporter.elements["tables"], "int bits"))
    assert data == [[1069547520, 1074790400, 3225419776, 1120403456]]


def test_interleaved_table_requires_native_stride_parity(tmp_path):
    exporter = _fixture(tmp_path)
    table = _by_title(exporter.elements["tables"], "interleaved curve")
    assert table["axes"]["x"]["labels"] == [10.0, 20.0, 30.0, 40.0]
    with pytest.raises(ValueError, match="Non-default XDF table strides"):
        exporter._read_table_data(table)


def test_typed_labels_are_shown_verbatim(tmp_path):
    exporter = _fixture(tmp_path)
    table = _by_title(exporter.elements["tables"], "typed labels with math")
    assert table["axes"]["x"]["labels"] == [0.0, 10.0, 20.0, 30.0]


def test_float_scalar_and_width_guard(tmp_path):
    exporter = _fixture(tmp_path)
    constants = exporter.elements["constants"]
    raw, value = exporter.read_constant(_by_title(constants, "float scalar"))
    assert (raw, value) == (0.125, 0.25)
    with pytest.raises(ValueError, match="32 or 64 bits"):
        exporter.read_constant(_by_title(constants, "bad float width"))


def test_native_tunerpro_export_keeps_typed_label_without_math(tmp_path):
    """TunerPro printed LABEL "0" with MATH 0.75*X-48 as 0 (not -48)."""
    xdf_setting = os.environ.get("KINGAI_TEST_MS42_XDF")
    native_setting = os.environ.get("KINGAI_TEST_MS42_NATIVE_EXPORT")
    if not xdf_setting or not native_setting:
        pytest.skip(
            "set KINGAI_TEST_MS42_XDF and KINGAI_TEST_MS42_NATIVE_EXPORT "
            "to run the optional native fixture comparison"
        )
    xdf_path = Path(xdf_setting)
    native_path = Path(native_setting)
    if not xdf_path.is_file() or not native_path.is_file():
        pytest.skip("configured MS42 native comparison fixtures are unavailable")
    native = native_path.read_text(encoding="latin-1")
    titles = ("ip_map_ini_ast__tco", "ip_maf_tco_cor__tco")
    for title in titles:
        block = native[native.index("TABLE: " + title):].splitlines()
        assert block[3].strip() == "0"
    binary = tmp_path / "zero_512k.bin"
    binary.write_bytes(bytes(512 * 1024))
    # This check concerns these literal-label tables only. Unrelated invalid
    # links elsewhere in a private definition must not broaden its claim.
    source_root = ET.parse(xdf_path).getroot()
    scoped_root = ET.Element("XDFFORMAT", source_root.attrib)
    header = source_root.find("XDFHEADER")
    if header is not None:
        scoped_root.append(header)
    for table in source_root.findall("XDFTABLE"):
        if table.findtext("title") in titles:
            scoped_root.append(table)
    scoped_path = tmp_path / "literal-labels-only.xdf"
    ET.ElementTree(scoped_root).write(scoped_path, encoding="utf-8")
    exporter = UniversalXDFExporter(str(scoped_path), str(binary))
    assert exporter.validate_bin_file()
    assert exporter.parse_xdf()
    for title in titles:
        table = _by_title(exporter.elements["tables"], title)
        assert table["axes"]["x"]["labels"] == [0.0]


def _per_cell_fixture(tmp_path):
    """Table with global + per-row equations using linked VARs (VS $51 pattern)."""
    data = bytearray(64)
    data[0x10] = 50        # Y source
    data[0x11] = 5         # Z source
    data[0x20:0x26] = bytes((1, 2, 3, 4, 9, 9))  # 3x2 cells; row2 uses global X*2
    binp = tmp_path / "pc.bin"; binp.write_bytes(bytes(data))
    xdf = tmp_path / "pc.xdf"
    xdf.write_text(
        '<XDFFORMAT version="1.70"><XDFHEADER><deftitle>pc</deftitle>'
        '<BASEOFFSET offset="0" subtract="0" /></XDFHEADER>'
        '<XDFCONSTANT uniqueid="0x900"><title>Ybase</title>'
        '<EMBEDDEDDATA mmedaddress="0x10" mmedelementsizebits="8" />'
        '<MATH equation="X"><VAR id="X" /></MATH></XDFCONSTANT>'
        '<XDFCONSTANT uniqueid="0x901"><title>Zstep</title>'
        '<EMBEDDEDDATA mmedaddress="0x11" mmedelementsizebits="8" />'
        '<MATH equation="X"><VAR id="X" /></MATH></XDFCONSTANT>'
        '<XDFTABLE uniqueid="0x902" flags="0x0"><title>ramp</title>'
        '<XDFAXIS id="x" uniqueid="0x0"><EMBEDDEDDATA mmedelementsizebits="8" />'
        '<indexcount>2</indexcount><LABEL index="0" value="0" /><LABEL index="1" value="1" />'
        '<MATH equation="X"><VAR id="X" /></MATH></XDFAXIS>'
        '<XDFAXIS id="y" uniqueid="0x0"><EMBEDDEDDATA mmedelementsizebits="8" />'
        '<indexcount>3</indexcount><LABEL index="0" value="0" /><LABEL index="1" value="1" />'
        '<LABEL index="2" value="2" /><MATH equation="X"><VAR id="X" /></MATH></XDFAXIS>'
        '<XDFAXIS id="z"><EMBEDDEDDATA mmedaddress="0x20" mmedelementsizebits="8" '
        'mmedrowcount="3" mmedcolcount="2" />'
        '<MATH equation="X*2"><VAR id="X" /></MATH>'
        '<MATH row="0" equation="Y"><VAR id="Y" type="link" linkid="0x900" /></MATH>'
        '<MATH row="1" equation="Y+Z"><VAR id="Y" type="link" linkid="0x900" />'
        '<VAR id="Z" type="link" linkid="0x901" /></MATH>'
        '</XDFAXIS></XDFTABLE></XDFFORMAT>', encoding="ascii")
    ex = UniversalXDFExporter(str(xdf), str(binp))
    assert ex.validate_bin_file() and ex.parse_xdf()
    return ex


def test_per_row_equations_override_global_with_precedence(tmp_path):
    ex = _per_cell_fixture(tmp_path)
    t = _by_title(ex.elements["tables"], "ramp")
    data = ex._read_table_data(t)
    # Zero-based row 0: "Y" = 50 for both cells (cell raw ignored).
    assert data[0] == [50.0, 50.0]
    # Zero-based row 1: "Y+Z" = 55 for both cells.
    assert data[1] == [55.0, 55.0]
    # data row 2: no row equation -> global "X*2" on raw cells 9,9 -> 18
    assert data[2] == [18.0, 18.0]


def test_dangling_var_link_does_not_abort_parse(tmp_path):
    """A table MATH linking to a missing VAR must not stop the whole file.

    The file parses, the good constant grades, and the bad table is reported as a
    per-element decode_error by run_diagnostics (community XDF defect handling).
    """
    data = bytearray(64)
    data[0x10] = 7
    data[0x20:0x24] = bytes((1, 2, 3, 4))
    binp = tmp_path / "d.bin"; binp.write_bytes(bytes(data))
    xdf = tmp_path / "d.xdf"
    xdf.write_text(
        '<XDFFORMAT version="1.70"><XDFHEADER><deftitle>d</deftitle>'
        '<BASEOFFSET offset="0" subtract="0" /></XDFHEADER>'
        '<XDFCONSTANT uniqueid="0x800"><title>good</title>'
        '<EMBEDDEDDATA mmedaddress="0x10" mmedelementsizebits="8" />'
        '<MATH equation="X"><VAR id="X" /></MATH></XDFCONSTANT>'
        '<XDFTABLE uniqueid="0x801" flags="0x0"><title>bad</title>'
        '<XDFAXIS id="x" uniqueid="0x0"><EMBEDDEDDATA mmedelementsizebits="8" />'
        '<indexcount>1</indexcount><LABEL index="0" value="0" />'
        '<MATH equation="X"><VAR id="X" /></MATH></XDFAXIS>'
        '<XDFAXIS id="y" uniqueid="0x0"><EMBEDDEDDATA mmedelementsizebits="8" />'
        '<indexcount>1</indexcount><LABEL index="0" value="0" />'
        '<MATH equation="X"><VAR id="X" /></MATH></XDFAXIS>'
        '<XDFAXIS id="z"><EMBEDDEDDATA mmedaddress="0x20" mmedelementsizebits="8" '
        'mmedrowcount="1" mmedcolcount="4" />'
        '<MATH equation="A+X"><VAR id="X" />'
        '<VAR id="A" type="link" linkid="0xDEAD" /></MATH>'
        '</XDFAXIS></XDFTABLE></XDFFORMAT>', encoding="ascii")
    ex = UniversalXDFExporter(str(xdf), str(binp))
    assert ex.validate_bin_file()
    assert ex.parse_xdf()  # was returning False before the lenient-link fix
    assert _by_title(ex.elements["constants"], "good")
    rep = ex.run_diagnostics()
    assert rep["elements_graded"] >= 2
    titles = [f["title"] for f in rep["findings"]["decode_error"]]
    assert "bad" in titles
