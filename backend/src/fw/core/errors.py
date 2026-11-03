from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette.exceptions import HTTPException as StarletteHTTPException


class ProblemDetail(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = "about:blank"
    title: str
    status: int
    detail: str
    code: str
    instance: str | None = None
    invalid_params: list[dict[str, Any]] | None = None


class ProblemDetailsException(Exception):
    def __init__(
        self,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        title: str = "Bad Request",
        detail: str = "The request could not be processed.",
        code: str = "BAD_REQUEST",
        invalid_params: list[dict[str, Any]] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.title = title
        self.detail = detail
        self.code = code
        self.invalid_params = invalid_params
        self.extra = extra or {}
        super().__init__(detail)


async def problem_exception_handler(request: Request, exc: ProblemDetailsException) -> JSONResponse:
    content: dict[str, Any] = {
        "type": "about:blank",
        "title": exc.title,
        "status": exc.status_code,
        "detail": exc.detail,
        "code": exc.code,
        "instance": request.url.path,
    }
    if exc.invalid_params:
        content["invalid_params"] = exc.invalid_params
    content.update(exc.extra)
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        media_type="application/problem+json",
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors: list[dict[str, Any]] = []
    for err in exc.errors():
        loc = [str(item) for item in err.get("loc", [])]
        errors.append(
            {
                "field": ".".join(loc),
                "reason": err.get("msg", "Validation error"),
                "type": err.get("type", "value_error"),
            }
        )

    content = {
        "type": "about:blank",
        "title": "Unprocessable Entity",
        "status": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "detail": "Request validation failed.",
        "code": "VALIDATION_ERROR",
        "instance": request.url.path,
        "invalid_params": errors,
    }
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=content,
        media_type="application/problem+json",
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    content = {
        "type": "about:blank",
        "title": exc.detail if isinstance(exc.detail, str) else "HTTP Exception",
        "status": exc.status_code,
        "detail": str(exc.detail),
        "code": f"HTTP_{exc.status_code}",
        "instance": request.url.path,
    }
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        media_type="application/problem+json",
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    content = {
        "type": "about:blank",
        "title": "Internal Server Error",
        "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
        "detail": "An unexpected error occurred. Please contact support.",
        "code": "INTERNAL_SERVER_ERROR",
        "instance": request.url.path,
    }
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=content,
        media_type="application/problem+json",
    )


class AppError(ProblemDetailsException):
    """Convenience domain error mapping to RFC 7807 ProblemDetailsException."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        title: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            status_code=status_code,
            title=title or code.replace("_", " ").title(),
            detail=message,
            code=code,
            extra=extra,
        )
