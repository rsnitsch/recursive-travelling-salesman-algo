from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("rfa-tsp")
except PackageNotFoundError:
    # Fallback if executed directly from source without editable install
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
