"""Compile MCF 1.0 course packages into static offline readers."""

from .compiler import CompileResult, SingleFileResult, compile_course, compile_single_file
from .model import ValidationError
from .parser import parse_course

__all__ = [
    "CompileResult",
    "SingleFileResult",
    "ValidationError",
    "compile_course",
    "compile_single_file",
    "parse_course",
]
__version__ = "1.0.0"
