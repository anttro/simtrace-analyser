"""Build the ready-to-run runtime zip for a GitHub release.

The wheel needs ``pip`` and the GitHub source archive carries the whole
repository (tests, CI, the gitignored ``tools/``).  This zip is the runtime
tree only: extract it anywhere, run ``start.bat`` on Windows or
``./start.sh`` elsewhere, and the server serves the bundled PWA.  Python 3
must be on ``PATH``; PyUSB is only needed for direct hardware capture.

The build is deliberately simple - the explicit include lists below are the
whole manifest, so nothing from ``tests/``, ``.github/``, ``pyproject.toml``
or a build directory can leak into the archive by accident.
"""

import argparse
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
# The script lives outside the packages; import the version from the checkout.
sys.path.insert(0, str(REPO))

from simtrace_analyser.version import __version__  # noqa: E402

# The Python packages (all modules, no caches).
PACKAGES = ('simtrace_analyser', 'simtrace2_pysniff')

# The PWA runtime files; ``tests/`` and ``package.json`` are dev-only.
FRONTEND = 'frontend'
FRONTEND_EXCLUDE = ('tests', 'package.json')

# Repo-root files that make the extracted tree usable.  LICENSE is included
# once the repository has one.
ROOT_FILES = (
    'start.sh',
    'start.bat',
    'sniff-start.sh',
    'sniff-start.bat',
    '70-simtrace2-pysniff.rules',
    'README.md',
    'README_RUS.md',
    'frontend.png',
    'architecture_en.svg',
    'architecture_ru.svg',
    'LICENSE',
)

# Skip editor/byte-code droppings wherever they appear.
SKIP_DIRS = ('__pycache__',)
SKIP_NAMES = ('.DS_Store',)
SKIP_SUFFIXES = ('.pyc',)


def _files(root):
    """Yield the regular files under *root*, sorted and cache-free."""
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name in SKIP_NAMES or path.suffix in SKIP_SUFFIXES:
            continue
        yield path


def _write_bat(zf, path, arcname):
    """Write a .bat entry with CRLF line endings.

    The checkout stores the batch files with LF, and cmd.exe mishandles a
    batch file whose lines end in a bare LF (labels and ``goto`` in
    particular), so the archive gets the Windows form.  The source files
    stay untouched.  ``writestr`` does not copy the file mode, so set it.
    """
    data = path.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
    info = zipfile.ZipInfo.from_file(path, arcname)
    info.external_attr = 0o644 << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    zf.writestr(info, data)


def build_zip(output_dir, version=None):
    """Write ``simtrace-analyser-<version>.zip`` into *output_dir*.

    Returns the archive path.  The zip has a single top-level directory
    ``simtrace-analyser-<version>/`` holding the runtime tree.
    """
    version = version or __version__
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / ('simtrace-analyser-%s.zip' % version)
    top = 'simtrace-analyser-%s' % version

    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as zf:
        for package in PACKAGES:
            for path in _files(REPO / package):
                zf.write(path, '%s/%s' % (top, path.relative_to(REPO).as_posix()))

        for path in _files(REPO / FRONTEND):
            rel = path.relative_to(REPO / FRONTEND)
            if rel.parts[0] in FRONTEND_EXCLUDE:
                continue
            zf.write(path, '%s/%s' % (top, path.relative_to(REPO).as_posix()))

        for name in ROOT_FILES:
            path = REPO / name
            if not path.is_file():
                # LICENSE is not in the repository yet; include it once it is.
                continue
            arcname = '%s/%s' % (top, name)
            if path.suffix == '.bat':
                _write_bat(zf, path, arcname)
            else:
                zf.write(path, arcname)

    return archive


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Build the runtime zip attached to a release')
    parser.add_argument('--output', default='dist', metavar='DIR',
                        help='directory for the archive (default: dist)')
    args = parser.parse_args(argv)

    archive = build_zip(args.output)
    with zipfile.ZipFile(archive) as zf:
        entries = len(zf.namelist())
    print(archive)
    print('%d entries' % entries)
    return 0


if __name__ == '__main__':
    sys.exit(main())
