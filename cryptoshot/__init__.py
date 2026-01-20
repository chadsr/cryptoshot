from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("cryptoshot")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

__description__ = "Retrieve cryptocurrency balances and values at a specific point in time."
