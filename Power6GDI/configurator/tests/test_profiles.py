import copy
import unittest

from power8gdi_configurator.project import CalibrationProject, default_project
from power8gdi_configurator.profiles import SPORT_GDI6, LEGACY_POWER8GDI
from power8gdi_configurator.simulator import DisplaySimulator, CHANNELS


def legacy_payload(version=2):
    payload = default_project().to_dict()
    payload.update(format_version=version, cylinders=8, name='Existing V8 tune')
    payload.pop('profile_id')
    payload.pop('imported_format_version')
    return payload


class ProfileContract(unittest.TestCase):
    def test_new_target_has_only_six_channels_and_two_motors(self):
        profile = default_project().profile
        self.assertEqual(profile.id, SPORT_GDI6)
        self.assertEqual((profile.cylinders, profile.di_channels, profile.pi_channels,
                          profile.ignition_channels), (6, 6, 6, 6))
        self.assertEqual((profile.hpfp_channels, profile.dbw_channels, profile.ewg_channels,
                          profile.lambda_channels, profile.knock_channels, profile.can_buses),
                         (2, 1, 1, 1, 2, 2))

    def test_legacy_roundtrip_preserves_every_map_and_does_not_retarget(self):
        for version in (1, 2):
            with self.subTest(version=version):
                payload = legacy_payload(version)
                payload['tables']['Boost / Target']['values'][1][2] = 223.45678
                before = copy.deepcopy(payload)
                project = CalibrationProject.from_dict(payload)
                self.assertEqual(project.cylinders, 8)
                self.assertEqual(project.profile_id, LEGACY_POWER8GDI)
                self.assertEqual(project.imported_format_version, version)
                self.assertIsNone(project.profile.lambda_channels)
                self.assertEqual(project.to_dict()['tables'], before['tables'])
                self.assertEqual(CalibrationProject.from_dict(project.to_dict()).to_dict(),
                                 project.to_dict())
                self.assertEqual(payload, before)

    def test_profile_or_count_tampering_rejected(self):
        for key, value in [('profile_id', 'unknown'), ('profile_id', LEGACY_POWER8GDI),
                           ('cylinders', 8), ('cylinders', 6.0), ('pumps', True),
                           ('pumps', 1), ('imported_format_version', 2)]:
            with self.subTest(key=key, value=value):
                payload = default_project().to_dict()
                payload[key] = value
                with self.assertRaises(ValueError):
                    CalibrationProject.from_dict(payload)

    def test_legacy_may_not_claim_six_cylinders_or_inject_new_profile(self):
        for change in ({'cylinders': 6}, {'profile_id': SPORT_GDI6}):
            payload = legacy_payload()
            payload.update(change)
            with self.assertRaises(ValueError):
                CalibrationProject.from_dict(payload)

    def test_v3_requires_explicit_profile(self):
        payload = default_project().to_dict()
        payload.pop('profile_id')
        with self.assertRaises(KeyError):
            CalibrationProject.from_dict(payload)


class SimulatorContract(unittest.TestCase):
    def test_disconnect_resets_time_and_no_samples_are_available(self):
        simulator = DisplaySimulator()
        with self.assertRaises(RuntimeError):
            simulator.step(.2)
        simulator.connect(SPORT_GDI6)
        simulator.step(.2)
        simulator.disconnect()
        self.assertEqual(simulator.time_s, 0)
        with self.assertRaises(RuntimeError):
            simulator.step(.2)

    def test_reconnect_and_values_are_deterministic_and_bounded(self):
        simulator = DisplaySimulator()
        simulator.connect(SPORT_GDI6)
        first = simulator.step(.2)
        for _ in range(1000):
            sample = simulator.step(.2)
            self.assertEqual(len(sample.values), len(CHANNELS))
            for channel, value in zip(CHANNELS, sample.values):
                self.assertLessEqual(channel.minimum, value)
                self.assertLessEqual(value, channel.maximum)
        simulator.disconnect()
        simulator.connect(SPORT_GDI6)
        self.assertEqual(first, simulator.step(.2))

    def test_invalid_steps_and_legacy_profile_rejected(self):
        simulator = DisplaySimulator()
        with self.assertRaises(ValueError):
            simulator.connect(LEGACY_POWER8GDI)
        self.assertFalse(simulator.connected)
        simulator.connect(SPORT_GDI6)
        for value in [0, -1, 1.1, True, float('inf'), float('nan'), '0.2']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                simulator.step(value)
        self.assertEqual(simulator.time_s, 0)
