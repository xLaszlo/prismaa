from __future__ import annotations


class PrismaError(Exception):
    pass


class RecordNotFoundError(PrismaError):
    pass


class UniqueViolationError(PrismaError):
    pass


class MissingRequiredValueError(PrismaError):
    pass
