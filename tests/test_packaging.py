"""Tests for the distributable packaging (bundled PWA, backend, manifest)."""

import os
import tempfile
import unittest

from simtrace_analyser.__main__ import _default_web_dir, _pick_web_dir

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _touch(path):
    with open(path, 'w') as f:
        f.write('')


class TestPickWebDir(unittest.TestCase):
    def test_prefers_packaged_pwa(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = os.path.join(tmp, 'simtrace_analyser')
            repo = os.path.join(tmp, 'repo')
            os.makedirs(os.path.join(pkg, 'web'))
            os.makedirs(os.path.join(repo, 'frontend'))
            _touch(os.path.join(pkg, 'web', 'index.html'))
            _touch(os.path.join(repo, 'frontend', 'index.html'))
            self.assertEqual(_pick_web_dir(pkg, repo),
                             os.path.join(pkg, 'web'))

    def test_falls_back_when_packaged_dir_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = os.path.join(tmp, 'simtrace_analyser')
            repo = os.path.join(tmp, 'repo')
            os.makedirs(pkg)
            os.makedirs(os.path.join(repo, 'frontend'))
            _touch(os.path.join(repo, 'frontend', 'index.html'))
            self.assertEqual(_pick_web_dir(pkg, repo),
                             os.path.join(repo, 'frontend'))

    def test_falls_back_when_packaged_dir_has_no_index(self):
        # A stale/empty simtrace_analyser/web directory must not shadow the
        # source checkout (e.g. an editable install of a half-built tree).
        with tempfile.TemporaryDirectory() as tmp:
            pkg = os.path.join(tmp, 'simtrace_analyser')
            repo = os.path.join(tmp, 'repo')
            os.makedirs(os.path.join(pkg, 'web'))
            os.makedirs(os.path.join(repo, 'frontend'))
            _touch(os.path.join(repo, 'frontend', 'index.html'))
            self.assertEqual(_pick_web_dir(pkg, repo),
                             os.path.join(repo, 'frontend'))


class TestDefaultWebDir(unittest.TestCase):
    def test_source_checkout(self):
        web = _default_web_dir()
        self.assertTrue(os.path.isfile(os.path.join(web, 'index.html')),
                        'no index.html in %s' % web)


class TestDistributionMetadata(unittest.TestCase):
    def _read(self, name):
        with open(os.path.join(REPO, name)) as f:
            return f.read()

    def test_build_backend_exists(self):
        pyproject = self._read('pyproject.toml')
        self.assertIn('build-backend = "setuptools.build_meta"', pyproject)
        self.assertNotIn('backends._legacy', pyproject)

    def test_manifest_ships_the_pwa(self):
        # The sdist carries frontend/, so a wheel built from it has the PWA.
        self.assertIn('graft frontend', self._read('MANIFEST.in'))

    def test_setup_py_bundles_the_pwa(self):
        setup_py = self._read('setup.py')
        self.assertIn('frontend', setup_py)
        self.assertIn('copytree', setup_py)
        self.assertIn("'web'", setup_py)
        self.assertIn("'build_py'", setup_py)
        self.assertIn('ignore_patterns', setup_py)


if __name__ == '__main__':
    unittest.main()
