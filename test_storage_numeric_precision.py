"""Explicit XDF integers must reach readers unchanged or fail closed."""

import json
import xml.etree.ElementTree as ET

import pytest

from tunerpro_exporter import UniversalXDFExporter


def loaded(tmp_path, body, header='<BASEOFFSET offset="0" subtract="0"/>'):
    definition = tmp_path / 'numeric source.xdf'
    binary = tmp_path / 'numeric source.bin'
    definition.write_text(
        f'<XDFFORMAT><XDFHEADER>{header}</XDFHEADER>{body}</XDFFORMAT>',
        encoding='utf-8',
    )
    binary.write_bytes(bytes(range(64)))
    exporter = UniversalXDFExporter(definition, binary)
    assert exporter.validate_bin_file()
    return exporter


def scalar(attributes):
    return (f'<XDFCONSTANT uniqueid="1"><title>Exact scalar</title>'
            f'<EMBEDDEDDATA {attributes}/><MATH equation="X"/></XDFCONSTANT>')


def test_uppercase_hex_address_flags_and_width_read_exact_signed_value(tmp_path):
    exporter = loaded(tmp_path, scalar(
        'mmedaddress="0X10" mmedelementsizebits="0x10" mmedtypeflags="0X03"'),
        '<BASEOFFSET offset="0X10" subtract="0X0"/>')
    exporter.bin_data = bytearray(exporter.bin_data)
    exporter.bin_data[32:34] = b'\xfe\xff'
    assert exporter.parse_xdf()
    item = exporter.elements['constants'][0]
    assert (item['address'], item['size'], item['type_flags']) == (16, 16, 3)
    assert exporter.read_constant(item) == (-2, -2)
    output = tmp_path / 'exact scalar.json'
    assert exporter.export_to_json(output)
    data = json.loads(output.read_text(encoding='utf-8'))
    assert data['scalars'][0]['value'] == -2


def test_hex_dimensions_and_strides_keep_every_table_cell(tmp_path):
    exporter = loaded(tmp_path, '''<XDFTABLE uniqueid="1"><title>Strided</title>
      <XDFAXIS id="z"><EMBEDDEDDATA mmedaddress="0X10"
        mmedelementsizebits="0X8" mmedrowcount="0X2" mmedcolcount="0x2"
        mmedmajorstridebits="0X20" mmedminorstridebits="0x8"/>
      <MATH equation="X"/></XDFAXIS></XDFTABLE>''')
    assert exporter.parse_xdf()
    table = exporter.elements['tables'][0]
    assert exporter._read_table_data(table) == [[16, 17], [20, 21]]


def test_embedded_axis_uses_exact_hex_storage_and_count(tmp_path):
    exporter = loaded(tmp_path, '''<XDFTABLE uniqueid="1"><title>Axis</title>
      <XDFAXIS id="x"><EMBEDDEDDATA mmedaddress="0X10"
        mmedelementsizebits="0X10" mmedtypeflags="0X02"
        mmedmajorstridebits="0X20"/>
        <indexcount>0X2</indexcount><embedinfo type="1"/><MATH equation="X"/>
      </XDFAXIS><XDFAXIS id="z"><EMBEDDEDDATA mmedaddress="0"
        mmedcolcount="2"/><MATH equation="X"/></XDFAXIS></XDFTABLE>''')
    assert exporter.parse_xdf()
    assert exporter.elements['tables'][0]['axes']['x']['labels'] == [4368.0, 5396.0]


def test_hex_flag_address_and_mask_do_not_fall_back_to_first_bit(tmp_path):
    exporter = loaded(tmp_path, '<XDFFLAG><title>Flag</title>'
        '<EMBEDDEDDATA mmedaddress="0X3"/><mask>0X04</mask></XDFFLAG>')
    assert exporter.parse_xdf()
    assert exporter.elements['flags'] == [
        {'title': 'Flag', 'address': 3, 'mask': 4, 'category': 'Uncategorized'}]


@pytest.mark.parametrize('field', [
    'mmedaddress', 'mmedelementsizebits', 'mmedtypeflags', 'mmedrowcount',
    'mmedcolcount', 'mmedmajorstridebits', 'mmedminorstridebits',
])
@pytest.mark.parametrize('value', ['', 'broken', '0XGG', '1.5'])
def test_explicit_invalid_storage_never_defaults_even_in_shared_parser(field, value):
    exporter = UniversalXDFExporter('unused.xdf', 'unused.bin')
    element = ET.fromstring(f'<XDFCONSTANT><EMBEDDEDDATA {field}="{value}"/></XDFCONSTANT>')
    with pytest.raises(ValueError, match='Invalid XDF'):
        exporter._parse_embedded_data(element)


@pytest.mark.parametrize('body,header', [
    ('<XDFFLAG address="bad"><title>Flag</title></XDFFLAG>', ''),
    ('<XDFFLAG address="0"><mask>broken</mask></XDFFLAG>', ''),
    ('<XDFFLAG address="0"><mask/></XDFFLAG>', ''),
    (scalar('mmedaddress="0"'), '<baseoffset>broken</baseoffset>'),
    ('''<XDFTABLE><title>Bad count</title><XDFAXIS id="x"><indexcount>broken</indexcount>
        </XDFAXIS><XDFAXIS id="z"><EMBEDDEDDATA mmedaddress="0"/>
        <MATH equation="X"/></XDFAXIS></XDFTABLE>''', ''),
])
def test_invalid_numeric_metadata_returns_parse_failure_without_outputs(tmp_path, body, header):
    exporter = loaded(tmp_path, body, header)
    before = exporter.xdf_path.read_bytes(), exporter.bin_path.read_bytes()
    assert not exporter.parse_xdf()
    assert (exporter.xdf_path.read_bytes(), exporter.bin_path.read_bytes()) == before
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        'numeric source.bin', 'numeric source.xdf']


def test_omitted_storage_and_address_defaults_remain_compatible(tmp_path):
    exporter = loaded(tmp_path, scalar(''))
    assert exporter.parse_xdf()
    assert exporter.read_constant(exporter.elements['constants'][0]) == (0, 0)
    missing = exporter._parse_embedded_data(ET.fromstring('<XDFCONSTANT/>'))
    assert missing['address'] is None
    assert (missing['size_bits'], missing['type_flags'], missing['major_stride'],
            missing['minor_stride'], missing['row_count'], missing['col_count']) == (8, 0, 0, 0, 1, 1)


def test_uppercase_hex_unsupported_flag_stays_rejected(tmp_path):
    exporter = loaded(tmp_path, scalar('mmedaddress="0" mmedtypeflags="0X04"'))
    assert exporter.parse_xdf()
    output = tmp_path / 'unsupported.json'
    assert not exporter.export_to_json(output)
    assert not output.exists()
