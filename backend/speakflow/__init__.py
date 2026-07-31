"""SpeakFlow backend package.

The package is organized as a modular monolith: business features own their
application ports and presentation adapters, while :mod:`speakflow.app` is the
only composition root.
"""

__all__ = ["app", "features", "shared"]
