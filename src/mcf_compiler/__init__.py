"""Validate and compile MCF 1.0 and 1.1 packages."""

from .compiler import CompileResult, SingleFileResult, compile_course, compile_single_file
from .model import ValidationError
from .package import (
    ParseOptions,
    ValidationResult,
    capabilities,
    parse_course,
    parse_package,
    parse_package_set,
    validate_capability_declaration,
    validate_package,
)

__all__ = [
    "CompileResult",
    "ParseOptions",
    "SingleFileResult",
    "ValidationError",
    "ValidationResult",
    "capabilities",
    "compile_course",
    "compile_single_file",
    "parse_course",
    "parse_package",
    "parse_package_set",
    "validate_capability_declaration",
    "validate_package",
]
__version__ = "1.1.0"
