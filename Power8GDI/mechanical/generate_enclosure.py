"""Compatibility entry point for the canonical concept assembly generator.

All geometry now comes from assembly_manifest.json. Use --output-dir to select
an export directory; this module has no import-time generation side effects.
"""
from build_assembly import main

if __name__ == '__main__':
    raise SystemExit(main())
