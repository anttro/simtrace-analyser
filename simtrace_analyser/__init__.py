"""simtrace_analyser — server side of SIMtrace Analyser.

Stores captured GSMTAP/PCAP APDU traffic in SQLite, decodes it, and serves
the PWA (``frontend/``) plus the HTTP API on a single origin.
"""

from .version import __version__

__all__ = ['__version__']
