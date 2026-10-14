"""Compatibility forwarder for the staged-file publication helpers.

pathlib-extensions owns these helpers under DESIGN D46. This module keeps the
names it exported before that move, so existing imports keep working (D18).
"""
from pathlib_extensions import publish_staged_file, resolve_publication_target

__all__ = ['publish_staged_file', 'resolve_publication_target']
