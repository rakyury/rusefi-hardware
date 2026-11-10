"""File-only tests of the reused racing_dash importer and its narrow adapter."""
import tempfile
import unittest
from pathlib import Path

from power8gdi_configurator.can_preview import load_can_preview, MAX_BYTES
from power8gdi_configurator.vendor.racing_dash.can_import import parse_dbc


DBC = '''VERSION ""
BO_ 256 Engine: 8 ECU
 SG_ RPM : 0|16@1+ (1,0) [0|8000] "rpm" Dash
 SG_ Temperature : 23|8@0+ (1,-40) [-40|215] "C" Dash
BO_ 2147483904 ExtendedEngine: 8 ECU
 SG_ Pressure : 0|16@1+ (0.5,0) [0|1000] "kPa" Dash
'''

CANX = '''<CANbuseXport><mob id="m_Engine" canbusID="600" ext="0" canbusIF="2" width="8">
<frame offset="0"><channel id="c_RPM" type="u16-le" byteOffset="0" multiplier="1" divider="1" unit="rpm"/></frame>
<frame offset="1"><channel id="c_Pressure" type="u16-be" byteOffset="2" multiplier="1" divider="10" unit="kPa"/></frame>
</mob></CANbuseXport>'''


class CANPreviewTests(unittest.TestCase):
    def preview(self, text, extension='.dbc', bus=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ('sample' + extension)
            path.write_text(text, encoding='utf-8')
            result = load_can_preview(path, bus)
            self.assertEqual(path.read_text(encoding='utf-8'), text)
            return result

    def test_dbc_identity_units_scaling_and_explicit_bus(self):
        result = self.preview(DBC, bus=1)
        self.assertEqual(len(result.signals), 3)
        self.assertEqual([s.can_id for s in result.signals],
                         ['0x100 (11 bit)', '0x100 (11 bit)', '0x100 (29 bit)'])
        self.assertTrue(all(s.bus == 'CAN2' for s in result.signals))
        self.assertEqual(result.signals[2].scale, 'raw × 1/2 + 0')
        self.assertEqual(result.signals[0].unit, 'rpm')
        self.assertIn('PREVIEW ONLY', result.warnings[0])

    def test_canx_keeps_bus_and_message_child_addressing(self):
        result = self.preview(CANX, '.canx')
        self.assertEqual([s.can_id for s in result.signals],
                         ['0x600 (11 bit)', '0x601 (11 bit)'])
        self.assertTrue(all(s.bus == 'CAN2' for s in result.signals))
        self.assertEqual(result.signals[1].scale, 'raw × 1/10 + 0')
        self.assertIn('compatibility parsing', result.warnings[1])
        self.assertTrue(all(s.bus == 'CAN1 + CAN2'
                            for s in self.preview(CANX, '.canx', bus=2).signals))

    def test_upstream_zero_scale_and_unbounded_scale_regressions(self):
        zero = self.preview(DBC.replace('(1,0)', '(0,0)'))
        self.assertEqual(zero.signals[0].scale, 'raw × 0/1 + 0')
        for scale in ['32768', '1e300', '1e999', '0.000000001']:
            with self.subTest(scale=scale):
                result = self.preview(DBC.replace('(1,0)', f'({scale},0)'))
                self.assertEqual(len(result.signals), 2)
                self.assertTrue(any('scale' in w for w in result.warnings))

    def test_fractional_offset_is_reported_instead_of_truncated(self):
        result = self.preview(DBC.replace('(1,0)', '(1,0.5)'))
        self.assertEqual(len(result.signals), 2)
        self.assertTrue(any('fractional' in w for w in result.warnings))

    def test_standard_extended_mux_selectors_do_not_collide(self):
        data = '''BO_ 256 A: 8 ECU
 SG_ AMux M : 0|8@1+ (1,0) "" ECU
 SG_ AValue m1 : 8|8@1+ (1,0) "" ECU
BO_ 2147483904 B: 8 ECU
 SG_ BMux M : 16|8@1+ (1,0) "" ECU
 SG_ BValue m2 : 24|8@1+ (1,0) "" ECU
'''
        result = parse_dbc(data)
        by_name = {s['name']: s['config'] for s in result['signals']}
        self.assertEqual(by_name['AValue']['mux_sel_bit'], 0)
        self.assertEqual(by_name['BValue']['mux_sel_bit'], 16)

    def test_invalid_id_or_unsupported_syntax_is_visible(self):
        result = self.preview(DBC.replace('BO_ 256 ', 'BO_ 4096 '))
        self.assertTrue(any('invalid standard/extended' in w for w in result.warnings))
        result = self.preview(DBC + '\n SG_ UNSUPPORTED : junk\n')
        self.assertTrue(any('UNSUPPORTED' in w for w in result.warnings))

    def test_entities_size_extension_and_bus_are_bounded(self):
        cases = [('<!DOCTYPE x [<!ENTITY a "text">]><x/>', '.canx', None),
                 ('x' * (MAX_BYTES + 1), '.dbc', None),
                 (DBC, '.txt', None), (DBC, '.dbc', True), (DBC, '.dbc', 3)]
        for text, extension, bus in cases:
            with self.subTest(extension=extension, bus=bus), self.assertRaises(ValueError):
                self.preview(text, extension, bus)
