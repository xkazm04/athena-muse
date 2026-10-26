"""The one error shape: `{error, reason}` with an HTTP status."""

from __future__ import annotations

from starlette.responses import JSONResponse

from athena.contracts import ErrorWord

STATUS: dict[ErrorWord, int] = {
    "bad_request": 400,
    "unknown_ref": 404,
    "space_busy": 409,
    "unauthorized": 401,
    "engine_unavailable": 503,
}


class ApiError(Exception):
    def __init__(self, error: ErrorWord, reason: str, status: int | None = None) -> None:
        super().__init__(f"{error}: {reason}")
        self.error: ErrorWord = error
        self.reason = reason
        self.status = status if status is not None else STATUS[error]

    def response(self) -> JSONResponse:
        return JSONResponse({"error": self.error, "reason": self.reason}, status_code=self.status)
