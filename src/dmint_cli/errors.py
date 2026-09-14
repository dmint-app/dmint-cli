"""Shared error types for dmint-cli with stable exit codes."""

from __future__ import annotations


class CLIError(Exception):
    """Base CLI error with an explicit exit code."""

    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code


class InputFileError(CLIError):
    def __init__(self, message: str) -> None:
        super().__init__(message, exit_code=3)


class APIError(CLIError):
    def __init__(self, message: str) -> None:
        super().__init__(message, exit_code=4)


class JSONExtractionError(CLIError):
    def __init__(self, message: str) -> None:
        super().__init__(message, exit_code=5)


class PolicyValidationError(CLIError):
    def __init__(self, message: str) -> None:
        super().__init__(message, exit_code=6)


class OutputWriteError(CLIError):
    def __init__(self, message: str) -> None:
        super().__init__(message, exit_code=7)
