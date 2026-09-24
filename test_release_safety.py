"""Synthetic regression cases for preserving inputs and rejecting ambiguous XDFs."""

import os
import sys

import pytest

from tunerpro_exporter import UniversalXDFExporter, main


def fixture(tmp_path, body='', header='', xdf_name='input.xdf'):
    xdf = tmp_path / xdf_name
    binary = tmp_path / 'input.bin'
    xdf.write_text(f'<XDFFORMAT><XDFHEADER>{header}</XDFHEADER>{body}</XDFFORMAT>',
                   encoding='utf-8')
    binary.write_bytes(bytes([11, 22, 33, 44]) + bytes(60))
    exporter = UniversalXDFExporter(str(xdf), str(binary))
    assert exporter.validate_bin_file()
    return exporter


def constant(attributes='mmedaddress="0"', uid='1'):
    return (f'<XDFCONSTANT uniqueid="{uid}"><title>Scalar</title>'
            f'<EMBEDDEDDATA {attributes}/><MATH equation="X"/></XDFCONSTANT>')


def table(maths, attributes=''):
    return ('<XDFTABLE uniqueid="table"><title>Table</title><XDFAXIS id="z">'
            f'<EMBEDDEDDATA mmedaddress="0" mmedrowcount="2" mmedcolcount="2" {attributes}/>'
            f'{maths}</XDFAXIS></XDFTABLE>')


@pytest.mark.parametrize('field', [
    'mmedelementsizebits', 'mmedtypeflags', 'mmedrowcount', 'mmedcolcount',
    'mmedmajorstridebits', 'mmedminorstridebits',
])
def test_malformed_storage_metadata_does_not_default(tmp_path, field):
    exporter = fixture(tmp_path, constant(f'mmedaddress="0" {field}="broken"'))
    assert not exporter.parse_xdf()


@pytest.mark.parametrize('attributes', [
    'offset="broken"', 'offset="0" subtract="wrong"', 'offset="0" subtract="2"',
])
def test_malformed_base_offset_does_not_default(tmp_path, attributes):
    exporter = fixture(tmp_path, constant(), f'<BASEOFFSET {attributes}/>')
    assert not exporter.parse_xdf()


@pytest.mark.parametrize('body', [
    constant('mmedaddress="broken"'),
    '<XDFFLAG><title>Bad</title><EMBEDDEDDATA mmedaddress="broken"/></XDFFLAG>',
    '<XDFFLAG><title>Missing</title></XDFFLAG>',
    '<XDFTABLE><title>Missing</title><XDFAXIS id="z"/></XDFTABLE>',
])
def test_invalid_addressed_objects_are_not_silently_omitted(tmp_path, body):
    exporter = fixture(tmp_path, body)
    assert not exporter.parse_xdf()


def test_omitted_optional_metadata_still_uses_defaults(tmp_path):
    exporter = fixture(tmp_path, constant())
    assert exporter.parse_xdf()
    assert exporter.read_constant(exporter.elements['constants'][0]) == (11, 11)


def test_addressless_constant_section_heading_is_preserved_as_supported(tmp_path):
    exporter = fixture(tmp_path, '<XDFCONSTANT><title>Section heading</title></XDFCONSTANT>')
    assert exporter.parse_xdf()
    assert exporter.elements['constants'] == []


def test_constant_with_direct_storage_defaults_omitted_address_zero(tmp_path):
    exporter = fixture(tmp_path, constant('mmedelementsizebits="8"'),
                       '<BASEOFFSET offset="1" subtract="0"/>')
    assert exporter.parse_xdf()
    item = exporter.elements['constants'][0]
    assert item['address'] == 0
    assert exporter.read_constant(item) == (22, 22)


def test_duplicate_unique_ids_cannot_select_last_object(tmp_path):
    exporter = fixture(tmp_path, constant('mmedaddress="0"') + constant('mmedaddress="1"'))
    assert not exporter.parse_xdf()


def test_sparse_single_row_equation_stays_on_second_row(tmp_path):
    exporter = fixture(tmp_path, table('<MATH row="1" equation="X*10"/>'))
    assert exporter.parse_xdf()
    assert exporter._read_table_data(exporter.elements['tables'][0]) == [[11, 22], [330, 440]]


def test_cell_row_column_global_precedence_is_zero_based(tmp_path):
    maths = ('<MATH equation="X"/><MATH col="0" equation="100"/>'
             '<MATH row="1" equation="200"/><MATH row="1" col="0" equation="300"/>')
    exporter = fixture(tmp_path, table(maths))
    assert exporter.parse_xdf()
    assert exporter._read_table_data(exporter.elements['tables'][0]) == [[100, 22], [300, 200]]


@pytest.mark.parametrize('maths', [
    '<MATH row="broken" equation="X"/>', '<MATH row="-1" equation="X"/>',
    '<MATH col="2" equation="X"/>', '<MATH row="2" equation="X"/>',
    '<MATH row="1" equation="X"/><MATH row="1" equation="2*X"/>',
    '<MATH equation="X"/><MATH equation="2*X"/>',
])
def test_invalid_scopes_fail_before_output_is_opened(tmp_path, maths):
    exporter = fixture(tmp_path, table(maths))
    assert exporter.parse_xdf()
    output = tmp_path / 'out.json'
    output.write_text('existing output', encoding='utf-8')
    assert not exporter.export_to_json(str(output))
    assert output.read_text(encoding='utf-8') == 'existing output'


def test_unproven_storage_flag_is_rejected(tmp_path):
    exporter = fixture(tmp_path, constant('mmedaddress="0" mmedtypeflags="0x04"'))
    assert exporter.parse_xdf()
    with pytest.raises(ValueError, match='Unsupported XDF storage flags'):
        exporter.read_constant(exporter.elements['constants'][0])


@pytest.mark.parametrize('method', [
    'export_to_text', 'export_to_json', 'export_to_markdown', 'export_to_csv', 'export_zeros_report',
])
@pytest.mark.parametrize('source_name', ['xdf_path', 'bin_path'])
def test_each_export_refuses_input_as_output(tmp_path, method, source_name):
    exporter = fixture(tmp_path, constant())
    assert exporter.parse_xdf()
    source = getattr(exporter, source_name)
    before = source.read_bytes()
    assert not getattr(exporter, method)(str(source))
    assert source.read_bytes() == before


def test_hardlink_output_cannot_overwrite_input(tmp_path):
    exporter = fixture(tmp_path, constant())
    assert exporter.parse_xdf()
    alias = tmp_path / 'alias.txt'
    try:
        os.link(exporter.bin_path, alias)
    except OSError as exc:
        pytest.skip(f'Hard links unavailable: {exc}')
    before = exporter.bin_path.read_bytes()
    assert not exporter.export_to_text(str(alias))
    assert exporter.bin_path.read_bytes() == before


@pytest.mark.parametrize(('xdf_name', 'extra'), [
    ('out.json', ['all']), ('out_zeros.md', ['all']),
    ('out_diagnostics.json', ['--diagnostics']),
])
def test_cli_preflights_all_outputs_and_sidecars_before_writing(tmp_path, monkeypatch, xdf_name, extra):
    exporter = fixture(tmp_path, constant(), xdf_name=xdf_name)
    before = exporter.xdf_path.read_bytes()
    monkeypatch.setattr(sys, 'argv', ['exporter', str(exporter.xdf_path),
        str(exporter.bin_path), str(tmp_path / 'out.txt'), *extra])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    assert exporter.xdf_path.read_bytes() == before
    assert not (tmp_path / 'out.txt').exists()


@pytest.mark.parametrize('flag', ['-h', '--help'])
def test_cli_help_succeeds_without_inputs(monkeypatch, flag):
    monkeypatch.setattr(sys, 'argv', ['exporter', flag])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0


def test_cli_rejects_unknown_option_before_writing(tmp_path, monkeypatch):
    exporter = fixture(tmp_path, constant())
    output = tmp_path / 'out.json'
    monkeypatch.setattr(sys, 'argv', ['exporter', str(exporter.xdf_path),
        str(exporter.bin_path), str(output), '--wrong-option'])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    assert not output.exists()


@pytest.mark.parametrize('value', ['broken', '2.5', 'NaN', 'Infinity', '1.0000000000000001'])
def test_legacy_nonempty_invalid_integer_cannot_default_or_truncate(value):
    with pytest.raises(ValueError, match='Invalid legacy XDF integer'):
        UniversalXDFExporter._legacy_int(value, 7)


@pytest.mark.parametrize(('value', 'expected'), [
    ('', 7), ('""', 7), ('  ', 7), ('0x10', 16), ('002', 2), ('2.0', 2),
    ('1e2', 100), ('9007199254740993.0', 9007199254740993),
])
def test_legacy_integer_defaults_and_integral_forms_remain_exact(value, expected):
    assert UniversalXDFExporter._legacy_int(value, 7) == expected


def test_legacy_malformed_rows_rejects_definition(tmp_path):
    exporter = fixture(tmp_path)
    exporter.xdf_path.write_text(
        'XDF\n1.110000\n%%HEADER%%\n    001005 DefTitle ="Synthetic"\n%%END%%\n'
        '%%TABLE%%\n    040005 Title ="Bad rows"\n    040100 Address =0\n'
        '    040300 Rows =2.5\n    040305 Cols =2\n%%END%%\n', encoding='ascii')
    assert not exporter.parse_xdf()


def embedded_axis(attributes='mmedaddress="8"', count='2', link=None):
    source = '<embedinfo type="1"/>' if link is None else f'<embedinfo type="3" {link}/>'
    count_xml = '' if count is None else f'<indexcount>{count}</indexcount>'
    return (f'<XDFAXIS id="x"><EMBEDDEDDATA {attributes}/>{count_xml}'
            f'{source}<MATH equation="X"/></XDFAXIS>')


@pytest.mark.parametrize(('attributes', 'count'), [
    ('mmedaddress="broken"', '2'), ('mmedaddress="0x1000"', '2'),
    ('mmedaddress="8"', None), ('mmedaddress="8"', 'broken'),
    ('mmedaddress="8"', '0'), ('mmedaddress="8"', '-1'),
    ('mmedaddress="8"', '4097'), ('mmedaddress="8" mmedelementsizebits="24"', '2'),
    ('mmedaddress="8" mmedmajorstridebits="3"', '2'),
    ('mmedaddress="8" mmedminorstridebits="16"', '2'),
])
def test_required_embedded_axis_cannot_disappear(tmp_path, attributes, count):
    body = table('<MATH equation="X"/>').replace(
        '</XDFTABLE>', embedded_axis(attributes, count) + '</XDFTABLE>')
    exporter = fixture(tmp_path, body)
    assert not exporter.parse_xdf()


def test_explicit_embedded_axis_omitted_address_defaults_zero_with_base_offset(tmp_path):
    axis = embedded_axis('mmedelementsizebits="16" mmedtypeflags="0x02"', '1')
    body = table('<MATH equation="X"/>').replace('</XDFTABLE>', axis + '</XDFTABLE>')
    exporter = fixture(tmp_path, body, '<BASEOFFSET offset="1" subtract="0"/>')
    assert exporter.parse_xdf()
    assert exporter.elements['tables'][0]['axes']['x']['labels'] == [8470.0]


def test_required_embedded_axis_without_storage_still_rejects(tmp_path):
    axis = '<XDFAXIS id="x"><indexcount>1</indexcount><embedinfo type="1"/></XDFAXIS>'
    body = table('<MATH equation="X"/>').replace('</XDFTABLE>', axis + '</XDFTABLE>')
    exporter = fixture(tmp_path, body)
    assert not exporter.parse_xdf()


@pytest.mark.parametrize('method', [
    'export_to_text', 'export_to_json', 'export_to_markdown', 'export_to_csv', 'export_zeros_report',
])
def test_export_rechecks_required_axis_before_opening_output(tmp_path, method):
    body = table('<MATH equation="X"/>').replace('</XDFTABLE>', embedded_axis() + '</XDFTABLE>')
    exporter = fixture(tmp_path, body)
    assert exporter.parse_xdf()
    # Z cells remain readable while the required X breakpoints no longer fit.
    exporter.bin_data = exporter.bin_data[:4]
    exporter.bin_size = 4
    output = tmp_path / 'existing.txt'
    output.write_text('preserve', encoding='utf-8')
    assert not getattr(exporter, method)(str(output))
    assert output.read_text(encoding='utf-8') == 'preserve'


@pytest.mark.parametrize(('link', 'count'), [('', '2'), ('linkobjid="1"', '0'),
                                                         ('linkobjid="1"', '-1')])
def test_required_linked_axis_needs_source_and_positive_count(tmp_path, link, count):
    body = table('<MATH equation="X"/>').replace(
        '</XDFTABLE>', embedded_axis(count=count, link=link) + '</XDFTABLE>')
    exporter = fixture(tmp_path, constant() + body)
    assert not exporter.parse_xdf()


def test_zero_uniqueids_are_unassigned_and_do_not_collide(tmp_path):
    exporter = fixture(tmp_path, constant('mmedaddress="0"', '0x0')
                       + constant('mmedaddress="1"', '0x0')
                       + constant('mmedaddress="2"', '0'))
    assert exporter.parse_xdf()
    assert [exporter.read_constant(item)[1] for item in exporter.elements['constants']] == [11, 22, 33]
    assert exporter.uniqueid_index == {}


def test_link_to_zero_cannot_select_unassigned_object(tmp_path):
    dependent = constant('mmedaddress="1"', '2').replace('<MATH equation="X"/>',
        '<MATH equation="Y"><VAR id="Y" type="link" linkid="0x0"/></MATH>')
    exporter = fixture(tmp_path, constant('mmedaddress="0"', '0x0') + dependent)
    assert exporter.parse_xdf()
    with pytest.raises(ValueError, match='missing XDF object'):
        exporter.read_constant(exporter.elements['constants'][1])


def patch_entry(address='0', datasize='1', patchdata='0B', basedata='00'):
    attrs = {'address': address, 'datasize': datasize, 'patchdata': patchdata, 'basedata': basedata}
    return '<XDFPATCHENTRY name="Entry" ' + ' '.join(
        f'{name}="{value}"' for name, value in attrs.items() if value is not None) + '/>'


@pytest.mark.parametrize(('entries', 'expected'), [
    (patch_entry() + patch_entry('1', patchdata='16'), 'applied'),
    (patch_entry(patchdata='00', basedata='0B') + patch_entry('1', patchdata='00', basedata='16'), 'not_applied'),
    (patch_entry() + patch_entry('1', patchdata='00', basedata='16'), 'partial'),
    (patch_entry() + patch_entry('1', patchdata='EE', basedata='FF'), 'unknown'),
    (patch_entry() + patch_entry('1000'), 'unknown'),
    (patch_entry(patchdata='00', basedata='0B') + patch_entry('1000'), 'unknown'),
    (patch_entry(datasize='2', patchdata='0b 16', basedata=None), 'applied'),
])
def test_patch_status_requires_every_entry_to_match(tmp_path, entries, expected):
    exporter = fixture(tmp_path, f'<XDFPATCH><title>Patch</title>{entries}</XDFPATCH>')
    assert exporter.parse_xdf()
    assert exporter.elements['patches'][0]['status'] == expected


@pytest.mark.parametrize('bad', [
    patch_entry(address='broken'), patch_entry(address=None), patch_entry(address='-1'),
    patch_entry(datasize='broken'), patch_entry(datasize='0'), patch_entry(datasize='-1'),
    patch_entry(datasize=None), patch_entry(patchdata='GG'), patch_entry(patchdata='B'),
    patch_entry(patchdata=''), patch_entry(patchdata='0B16'), patch_entry(basedata='GG'),
    patch_entry(basedata=''), patch_entry(patchdata=None, basedata=None),
])
def test_malformed_patch_entry_cannot_be_silently_skipped(tmp_path, bad):
    exporter = fixture(tmp_path, f'<XDFPATCH><title>Patch</title>{patch_entry()}{bad}</XDFPATCH>')
    assert not exporter.parse_xdf()


def test_parse_error_identifies_required_axis_table(tmp_path, caplog):
    body = table('<MATH equation="X"/>').replace(
        '</XDFTABLE>', embedded_axis(link='') + '</XDFTABLE>')
    exporter = fixture(tmp_path, body)
    assert not exporter.parse_xdf()
    assert "Table 'Table' (uniqueid='table'), axis 'x'" in caplog.text
