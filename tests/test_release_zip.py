"""Tests for the ready-to-run release zip (scripts/build_release_zip.py)."""

import importlib.util
import re
import tempfile
import unittest
import zipfile
from pathlib import Path

from simtrace_analyser.version import __version__

REPO = Path(__file__).resolve().parents[1]

# scripts/ is not a package, so load the builder from its path.
_spec = importlib.util.spec_from_file_location(
    'build_release_zip', REPO / 'scripts' / 'build_release_zip.py')
build_release_zip = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_release_zip)


class TestReleaseZip(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.archive = build_release_zip.build_zip(cls._tmp.name)
        with zipfile.ZipFile(cls.archive) as zf:
            cls.names = zf.namelist()

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_name_and_single_top_level_directory(self):
        top = 'simtrace-analyser-%s' % __version__
        self.assertEqual(self.archive.name, top + '.zip')
        for name in self.names:
            self.assertTrue(name.startswith(top + '/'),
                            '%s is outside %s/' % (name, top))

    def test_required_entries(self):
        top = 'simtrace-analyser-%s' % __version__
        for rel in (
                'simtrace_analyser/__main__.py',
                'simtrace_analyser/version.py',
                'simtrace2_pysniff/__main__.py',
                'frontend/index.html',
                'frontend/sw.js',
                'frontend/manifest.json',
                'start.sh',
                'start.bat',
                'sniff-start.sh',
                'sniff-start.bat',
                '70-simtrace2-pysniff.rules',
                'README.md'):
            self.assertIn('%s/%s' % (top, rel), self.names)

    def test_dev_only_entries_are_excluded(self):
        for name in self.names:
            self.assertNotIn('/tests/', name)
            self.assertNotIn('/__pycache__/', name)
            self.assertNotIn('.pyc', name)
            self.assertNotIn('/.git', name)
            self.assertNotIn('/.github/', name)
        self.assertNotIn(
            'simtrace-analyser-%s/frontend/package.json' % __version__,
            self.names)
        self.assertNotIn(
            'simtrace-analyser-%s/pyproject.toml' % __version__, self.names)

    def test_precache_files_are_in_the_zip(self):
        # Drift guard: every asset the service worker precaches must travel
        # with the PWA, otherwise an offline install fails on a fresh extract.
        text = (REPO / 'frontend' / 'sw.js').read_text()
        match = re.search(r'PRECACHE\s*=\s*\[(.*?)\]', text, re.S)
        self.assertIsNotNone(match, 'no PRECACHE array in frontend/sw.js')
        assets = re.findall(r"'([^']+)'", match.group(1))
        self.assertTrue(assets)
        top = 'simtrace-analyser-%s' % __version__
        for asset in assets:
            self.assertIn('%s/frontend/%s' % (top, asset), self.names,
                          'precached %s is missing from the zip' % asset)

    def test_batch_files_use_crlf(self):
        with zipfile.ZipFile(self.archive) as zf:
            bats = [n for n in self.names if n.endswith('.bat')]
            self.assertTrue(bats)
            for name in bats:
                data = zf.read(name)
                self.assertIn(b'\r\n', data, name)
                self.assertNotIn(b'\n', data.replace(b'\r\n', b''),
                                 '%s has a bare LF' % name)

    def test_shell_script_is_lf_and_executable(self):
        name = 'simtrace-analyser-%s/start.sh' % __version__
        with zipfile.ZipFile(self.archive) as zf:
            info = zf.getinfo(name)
            data = zf.read(name)
        self.assertNotIn(b'\r\n', data)
        self.assertTrue(info.external_attr >> 16 & 0o100,
                        'start.sh lost its executable bit')


if __name__ == '__main__':
    unittest.main()
