"""simtrace2-pysniff — Python replacement for simtrace2-sniff.

Capture utility bundled with SIMtrace Analyser.  Hardware access (PyUSB) is
imported lazily, so the GSMTAP/PCAP codec modules can be used without libusb.
"""

from simtrace_analyser.version import __version__

__all__ = [
    'SniffSession',
    'DeviceDisconnected',
    'find_sniffer_device',
    'parse_message',
    'SniffMessage',
    'GsmtapSender',
    'GsmtapReceiver',
    'PcapWriter',
    'FileDumper',
    'format_message',
    '__version__',
]

_LAZY_IMPORTS = {
    'SniffSession': ('.device', 'SniffSession'),
    'DeviceDisconnected': ('.device', 'DeviceDisconnected'),
    'find_sniffer_device': ('.device', 'find_sniffer_device'),
    'parse_message': ('.protocol', 'parse_message'),
    'SniffMessage': ('.protocol', 'SniffMessage'),
    'GsmtapSender': ('.gsmtap', 'GsmtapSender'),
    'GsmtapReceiver': ('.gsmtap', 'GsmtapReceiver'),
    'PcapWriter': ('.pcap', 'PcapWriter'),
    'FileDumper': ('.dump', 'FileDumper'),
    'format_message': ('.dump', 'format_message'),
}


def __getattr__(name):
    """Import utility symbols on first use (PEP 562)."""
    try:
        module_name, attr = _LAZY_IMPORTS[name]
    except KeyError:
        raise AttributeError(f'module {__name__!r} has no attribute {name!r}') from None
    from importlib import import_module
    value = getattr(import_module(module_name, __name__), attr)
    globals()[name] = value
    return value
