"""Tests for the bash launchers' Windows-hosted-shell guard."""

import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BASH = shutil.which('bash')

LAUNCHERS = (
    ('start.sh', 'start.bat'),
    ('sniff-start.sh', 'sniff-start.bat'),
)


@unittest.skipUnless(BASH, 'bash is not installed')
class TestWindowsGuard(unittest.TestCase):
    def _run_as_windows(self, script):
        """Run *script* with a fake `uname -s` naming a mingw host."""
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / 'uname'
            fake.write_text('#!/bin/sh\necho MINGW64_NT-10.0\n')
            fake.chmod(0o755)
            env = dict(os.environ)
            env['PATH'] = tmp + os.pathsep + env.get('PATH', '')
            return subprocess.run(
                [BASH, str(REPO / script)], cwd=REPO, env=env,
                capture_output=True, text=True, timeout=30)

    def test_guard_exits_and_names_the_bat_launcher(self):
        for script, bat in LAUNCHERS:
            with self.subTest(script=script):
                res = self._run_as_windows(script)
                self.assertEqual(res.returncode, 2, res.stderr)
                self.assertIn(
                    'Error: %s is the Linux/macOS helper and cannot run on '
                    'Windows' % script, res.stderr)
                self.assertIn(
                    '(WSL / MSYS2 / MinGW / Cygwin detected).', res.stderr)
                self.assertIn(
                    'Use %s from a Windows command prompt (cmd.exe / '
                    'PowerShell) instead.' % bat, res.stderr)

    def test_guard_detects_wsl_and_native_windows_shells(self):
        # The mingw/msys/cygwin branch is exercised above; pin the WSL branch
        # and the exit code so a refactor cannot drop either detection.
        for script, _ in LAUNCHERS:
            with self.subTest(script=script):
                src = (REPO / script).read_text()
                self.assertIn('grep -qi microsoft /proc/version', src)
                self.assertIn('MINGW|MSYS|CYGWIN', src)
                self.assertIn('exit 2', src)
                self.assertLess(src.index('Windows guard'),
                                src.index('PROJECT_DIR='),
                                'the guard must run before the launcher setup')

    def test_shell_syntax(self):
        for script, _ in LAUNCHERS:
            with self.subTest(script=script):
                res = subprocess.run(
                    [BASH, '-n', str(REPO / script)],
                    capture_output=True, text=True)
                self.assertEqual(res.returncode, 0, res.stderr)


if __name__ == '__main__':
    unittest.main()
