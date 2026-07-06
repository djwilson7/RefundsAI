"""Compatibility shim for AI chat service imports.

The implementation lives in the sibling ``ai_chat`` package. Python resolves the
package for normal imports when both this file and the package directory exist;
this file remains intentionally thin for tools that inspect the legacy module path.
"""

from __future__ import annotations

from refunds_ai_api.services.ai_chat import *  # noqa: F403
