"""Legitimate per-cell address views must not vanish behind a clean export."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from tunerpro_exporter import UniversalXDFExporter

def virtual_view(uid,title,address,width):
    return f'''<XDFTABLE uniqueid="{uid}"><title>{title}</title>
      <XDFAXIS id="x"><indexcount>1</indexcount><LABEL index="0" value="Value" /></XDFAXIS>
      <XDFAXIS id="y"><indexcount>1</indexcount><LABEL index="0" value="Identity" /></XDFAXIS>
      <XDFAXIS id="z"><EMBEDDEDDATA mmedelementsizebits="16" mmedrowcount="1" />
        <MATH equation="X"><VAR id="X" /></MATH>
        <MATH row="1" col="1" equation="X"><VAR id="X" type="address" address="{address}" sizeinbits="{width}" /></MATH>
      </XDFAXIS></XDFTABLE>'''

class OmittedDefinitionCompleteness(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.binary=self.root/"fixture.bin";self.binary.write_bytes(bytes(range(256))*16)
        self.xdf=self.root/"fixture.xdf"
        body='''<XDFTABLE uniqueid="0x1"><title>Addressed table</title>
            <XDFAXIS id="x"><indexcount>2</indexcount></XDFAXIS>
            <XDFAXIS id="y"><indexcount>2</indexcount></XDFAXIS>
            <XDFAXIS id="z"><EMBEDDEDDATA mmedaddress="0x100" mmedelementsizebits="8" mmedrowcount="2" mmedcolcount="2" />
            <MATH equation="X"><VAR id="X" /></MATH></XDFAXIS></XDFTABLE>'''
        virtual=''.join([virtual_view("0x7D7F","Operating System","0x504",32),
            virtual_view("0x4621","Calibration Segment Information","0x800",32),
            virtual_view("0x6DC4","Stored Segment Checksums","0x802",16)])
        self.xdf.write_text('<XDFFORMAT version="1.70"><XDFHEADER><deftitle>omission fixture</deftitle></XDFHEADER>'+body+virtual+'</XDFFORMAT>')
        self.exporter=UniversalXDFExporter(str(self.xdf),str(self.binary))
        self.assertTrue(self.exporter.validate_bin_file());self.assertTrue(self.exporter.parse_xdf())

    def tearDown(self):self.temp.cleanup()

    def test_all_declared_views_are_named_in_incomplete_diagnostics(self):
        report=self.exporter.run_diagnostics();coverage=report['definition_completeness']
        self.assertEqual(coverage['declared_tables'],4);self.assertEqual(coverage['extracted_tables'],1)
        self.assertEqual(coverage['omitted_count'],3);self.assertFalse(report['validation_complete'])
        self.assertEqual(report['grade'],'INCOMPLETE');self.assertEqual(report['refuted_count'],0)
        self.assertEqual({r['uniqueid'] for r in coverage['omitted_definitions']},{'0x7D7F','0x4621','0x6DC4'})
        self.assertEqual(coverage['omitted_definitions'][0]['cell_math'][0]['variables'][0]['address'],'0x504')

    def test_normal_value_export_refuses_silent_omission_before_writing(self):
        target=self.root/'values.json'
        self.assertFalse(self.exporter.export_to_json(str(target)))
        self.assertFalse(target.exists())

    def test_valid_addressed_table_still_exports_its_real_values(self):
        text=self.xdf.read_text();start=text.index('<XDFTABLE uniqueid="0x7D7F"')
        self.xdf.write_text(text[:start]+'</XDFFORMAT>')
        exporter=UniversalXDFExporter(str(self.xdf),str(self.binary))
        self.assertTrue(exporter.validate_bin_file());self.assertTrue(exporter.parse_xdf())
        target=self.root/'complete.json';self.assertTrue(exporter.export_to_json(str(target)))
        self.assertEqual(json.loads(target.read_text())['tables'][0]['data'],[[0,1],[2,3]])
        self.assertTrue(exporter.run_diagnostics()['validation_complete'])

    def test_cli_returns_failure_with_omitted_titles_and_no_values_file(self):
        target=self.root/'cli.json'
        run=subprocess.run([sys.executable,'-m','tunerpro_exporter',
            str(self.xdf),str(self.binary),str(target),'json','--no-zerosexport'],capture_output=True,text=True,encoding='utf-8')
        self.assertNotEqual(run.returncode,0);self.assertFalse(target.exists())
        for title in ['Operating System','Calibration Segment Information','Stored Segment Checksums']:
            self.assertIn(title,run.stderr)

if __name__=='__main__':unittest.main()
