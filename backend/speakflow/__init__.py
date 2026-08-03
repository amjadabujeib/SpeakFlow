"""SpeakFlow backend package.

The package is organized as a modular monolith: business features own their
application ports and presentation adapters, while :mod:`speakflow.app` is the
only composition root.
"""

APP_RELEASE = "1.0.0"

__all__ = ["APP_RELEASE", "app", "features", "shared"]
