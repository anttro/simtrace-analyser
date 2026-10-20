"""Bundle the PWA into the installed package.

The metadata lives in pyproject.toml; this file only adds the build step that
copies ``frontend/`` into ``simtrace_analyser/web/`` inside the build tree, so
a wheel (or an install from it) serves the same UI as a source checkout.
``setup.py`` is part of the sdist, and the source directory is resolved
relative to this file, so a wheel built from the unpacked sdist gets the PWA
too.
"""

import os
import shutil

from setuptools import setup
from setuptools.command.build_py import build_py

HERE = os.path.dirname(os.path.abspath(__file__))
WEB_SOURCE = os.path.join(HERE, 'frontend')
WEB_TARGET = os.path.join('simtrace_analyser', 'web')


class BuildPy(build_py):
    def run(self):
        super().run()
        if not os.path.isdir(WEB_SOURCE):
            raise RuntimeError(
                'the PWA source directory is missing: %s (a build must not '
                'ship a package without its user interface)' % WEB_SOURCE)
        target = os.path.join(self.build_lib, WEB_TARGET)
        shutil.copytree(
            WEB_SOURCE, target, dirs_exist_ok=True,
            ignore=shutil.ignore_patterns('tests', '__pycache__', '*.pyc'))


setup(cmdclass={'build_py': BuildPy})
