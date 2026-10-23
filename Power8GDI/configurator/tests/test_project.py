import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from power8gdi_configurator.project import default_project,CalibrationProject,CalibrationTable


class ProjectContract(unittest.TestCase):
    def setUp(self):
        self.project=default_project()

    def test_default_dimensions(self):
        self.assertEqual((8,2),(self.project.cylinders,self.project.pumps))
        self.assertEqual(11,len(self.project.tables))
        self.assertEqual(11,len(self.project.tables['Boost / Target'].x_bins))

    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/'calibration.p8gdi.json'
            self.project.save(file)
            other=CalibrationProject.load(file)
            self.assertEqual(other.to_dict(),self.project.to_dict())

    def test_save_preserves_existing_tmp_sidecar(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'calibration.json'
            sidecar = Path(directory) / 'calibration.json.tmp'
            sidecar.write_text('unrelated recovery data', encoding='utf-8')
            self.project.save(target)
            self.assertTrue(sidecar.exists(), 'Save consumed an existing sidecar')
            self.assertEqual(sidecar.read_text(encoding='utf-8'), 'unrelated recovery data')
            self.assertEqual(CalibrationProject.load(target).to_dict(), self.project.to_dict())

    def test_failed_replace_preserves_target_and_cleans_owned_temp(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'calibration.json'
            target.write_text('original data', encoding='utf-8')
            with patch.object(Path, 'replace', side_effect=OSError('injected replacement failure')):
                with self.assertRaises(OSError):
                    self.project.save(target)
            self.assertEqual(target.read_text(encoding='utf-8'), 'original data')
            self.assertEqual(list(Path(directory).iterdir()), [target])

    def test_interpolation_center(self):
        t=CalibrationTable('linear','test','x','y','bar',
                  [0,100],[0,200],[[10,20],[30,40]],0,100)
        self.assertAlmostEqual(25,t.interpolate(50,100))
        self.assertEqual(10,t.interpolate(-500,-900))
        self.assertEqual(40,t.interpolate(10000,10000))

    def test_reject_axis_nonmonotonic(self):
        d=self.project.to_dict()
        d['tables']['Boost / Target']['x_bins'][1]=0
        with self.assertRaises(ValueError):CalibrationProject.from_dict(d)

    def test_reject_nonfinite(self):
        with self.assertRaises(ValueError):
            self.project.tables['Boost / Target'].set_value(0,0,float('nan'))

    def test_reject_out_of_range(self):
        with self.assertRaises(ValueError):
            self.project.tables['Ignition / Advance'].set_value(0,0,1000)

    def test_reject_structural_mismatch(self):
        d=self.project.to_dict();d['tables']['Boost / Target']['values'].pop()
        with self.assertRaises(ValueError):CalibrationProject.from_dict(d)

    def test_reject_invalid_version(self):
        d=self.project.to_dict();d['format_version']=99
        with self.assertRaises(ValueError):CalibrationProject.from_dict(d)

    def test_injector_count_does_not_change(self):
        d=self.project.to_dict();d['cylinders']=6
        with self.assertRaises(ValueError):CalibrationProject.from_dict(d)

    def test_never_allow_bool_as_number(self):
        with self.assertRaises(ValueError):
            self.project.tables['Fuel / VE'].set_value(0,0,True)

if __name__=='__main__':unittest.main()
