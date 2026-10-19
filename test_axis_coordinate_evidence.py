"""Keep native text-export parity without inventing numeric breakpoints."""
import json
import xml.etree.ElementTree as ET

import pytest

from tunerpro_exporter import UniversalXDFExporter


def axis(labels, source=None):
    node = ET.Element('XDFAXIS', id='y')
    if source:
        ET.SubElement(node, 'embedinfo', type=source)
    for i, value in enumerate(labels):
        ET.SubElement(node, 'LABEL', index=str(i), value=value)
    return node


@pytest.mark.parametrize('label', ['no less than 0.244', 'only + numbers here 0.000',
                                  'et cetera 0.732', '0x20'])
def test_prose_is_not_zero_or_a_trailing_number(label):
    result = UniversalXDFExporter._axis_coordinate_evidence(axis([label]), [0.0])
    assert result['coordinate_values'] == [None]
    assert not result['numeric_coordinates_complete']
    assert result['coordinate_issues'][0]['display_label'] == label


def test_true_zero_and_scientific_labels_remain_numeric():
    result = UniversalXDFExporter._axis_coordinate_evidence(
        axis(['0.000', '-0.25', '1.2e3']), [0, -0.25, 1200])
    assert result['coordinate_values'] == [0, -0.25, 1200]
    assert result['numeric_coordinates_complete']


@pytest.mark.parametrize('label', ['NaN', 'inf', '-inf'])
def test_nonfinite_literal_is_held(label):
    result = UniversalXDFExporter._axis_coordinate_evidence(axis([label]), [0])
    assert result['coordinate_values'] == [None]
    assert result['coordinate_issues'][0]['reason'] == 'nonfinite_coordinate'


def test_missing_labels_are_not_zero_breakpoints():
    result = UniversalXDFExporter._axis_coordinate_evidence(axis(['0']), [0, 0])
    assert result['coordinate_values'] == [0, None]
    assert result['coordinate_issues'][0]['reason'] == 'missing_numeric_label'


@pytest.mark.parametrize('source', ['1', '3'])
def test_embedded_or_linked_values_ignore_unused_prose(source):
    result = UniversalXDFExporter._axis_coordinate_evidence(
        axis(['unused prose'], source), [10, 20])
    assert result['coordinate_values'] == [10, 20]
    assert result['numeric_coordinates_complete']


def test_empty_axis_does_not_claim_numeric_completeness():
    result = UniversalXDFExporter._axis_coordinate_evidence(axis([]), [])
    assert not result['numeric_coordinates_complete']


def fixture(tmp_path):
    binary = tmp_path / 'probe.bin'
    binary.write_bytes(bytes(range(64)))
    xdf = tmp_path / 'probe.xdf'
    xdf.write_text('''<XDFFORMAT><XDFHEADER><deftitle>probe</deftitle>
      <BASEOFFSET offset="0" subtract="0"/></XDFHEADER>
      <XDFTABLE uniqueid="0x10F1"><title>Low pulse probe</title>
        <XDFAXIS id="x"><indexcount>1</indexcount><LABEL value="0"/>
          <MATH equation="X"/></XDFAXIS>
        <XDFAXIS id="y"><indexcount>4</indexcount>
          <LABEL value="only + numbers here 0.000"/>
          <LABEL value="no less than 0.244"/><LABEL value="0.488"/>
          <LABEL value="0.732"/><MATH equation="X"/></XDFAXIS>
        <XDFAXIS id="z"><EMBEDDEDDATA mmedaddress="0x10"
          mmedelementsizebits="8" mmedrowcount="4" mmedcolcount="1"/>
          <decimalpl>2</decimalpl><MATH equation="X"/></XDFAXIS>
      </XDFTABLE></XDFFORMAT>''', encoding='ascii')
    exporter = UniversalXDFExporter(str(xdf), str(binary))
    assert exporter.validate_bin_file() and exporter.parse_xdf()
    return exporter


def test_json_preserves_native_labels_and_reports_coordinate_gaps(tmp_path):
    exporter = fixture(tmp_path)
    output = tmp_path / 'probe.json'
    assert exporter.export_to_json(str(output))
    result = json.loads(output.read_text())['tables'][0]
    y = result['axes']['y']
    assert y['labels'] == [0, 0, 0.488, 0.732]
    assert y['coordinate_values'] == [None, None, 0.488, 0.732]
    assert result['data'] == [[16], [17], [18], [19]]
    assert y['display_labels'][1] == 'no less than 0.244'


def test_json_flip_keeps_evidence_and_cells_aligned(tmp_path):
    exporter = fixture(tmp_path)
    exporter.flip_rpm = True
    output = tmp_path / 'flipped.json'
    assert exporter.export_to_json(str(output))
    result = json.loads(output.read_text())['tables'][0]
    y = result['axes']['y']
    assert y['coordinate_values'] == [0.732, 0.488, None, None]
    assert [issue['index'] for issue in y['coordinate_issues']] == [2, 3]
    assert result['data'] == [[19], [18], [17], [16]]
    assert exporter.elements['tables'][0]['axes']['y']['coordinate_values'][0] is None


def test_both_axis_flips_reverse_metadata_without_mutating_original():
    exporter = UniversalXDFExporter.__new__(UniversalXDFExporter)
    exporter.flip_rpm = exporter.flip_load = True
    evidence = UniversalXDFExporter._axis_coordinate_evidence(axis(['text', '2']), [0, 2])
    axes = {aid: {'labels': [0, 2], 'display_labels': ['text', '2'], **evidence}
            for aid in ('x', 'y')}
    data, flipped = exporter._apply_axis_flips([[1, 2], [3, 4]], axes)
    assert data == [[4, 3], [2, 1]]
    for aid in ('x', 'y'):
        assert flipped[aid]['coordinate_values'] == [2, None]
        assert flipped[aid]['coordinate_issues'][0]['index'] == 1
        assert axes[aid]['coordinate_issues'][0]['index'] == 0
