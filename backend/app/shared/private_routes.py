"""Apply private response caching to successful and handled route errors."""

from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException
from fastapi.responses import JSONResponse

from app.core.exceptions import AppError


class PrivateRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def private(request):
            try:
                response = await handler(request)
            except RequestValidationError:
                # Extra JSON key names can themselves contain private input.
                response = JSONResponse(status_code=422, content=AppError(
                    "VALIDATION_ERROR", "Request validation failed.", status_code=422).to_payload())
            except (AppError, HTTPException) as exc:
                error_handler = request.app.exception_handlers.get(type(exc)) or request.app.exception_handlers[HTTPException]
                response = await error_handler(request, exc)
            response.headers["Cache-Control"] = "no-store"
            return response
        return private
