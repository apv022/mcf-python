"""Compile MCF 1.0 course packages into static offline readers."""

from .compiler import CompileResult, compile_course
from .model import ValidationError
from .parser import parse_course

__all__ = ["CompileResult", "ValidationError", "compile_course", "parse_course"]
__version__ = "1.0.0"
