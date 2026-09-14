"""Dmint CLI package."""

from .api import OpenAICompatClient, mask_secret
from .compile_policy import compile_policy_file, main_compile
from .create_mcp_policy import main_create_mcp, run_create_mcp_policy_wizard
from .create_policy import main_create, run_create_policy_wizard
from .errors import (
    APIError,
    CLIError,
    InputFileError,
    JSONExtractionError,
    OutputWriteError,
    PolicyValidationError,
)
from .verify_policy import main_verify, verify_policy_file

__version__ = "0.3.0"

__all__ = [
    "APIError",
    "CLIError",
    "InputFileError",
    "JSONExtractionError",
    "OpenAICompatClient",
    "OutputWriteError",
    "PolicyValidationError",
    "__version__",
    "compile_policy_file",
    "main_compile",
    "main_create",
    "main_create_mcp",
    "main_verify",
    "mask_secret",
    "run_create_mcp_policy_wizard",
    "run_create_policy_wizard",
    "verify_policy_file",
]
