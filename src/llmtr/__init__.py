"""llmtr: translate, fix or re-tone the selected text with a local Ollama model.

The console script ``llmtr = "llmtr:main"`` points here. Design: ``docs/architecture.md``.
"""

from llmtr.cli import main

__all__ = ["main"]
