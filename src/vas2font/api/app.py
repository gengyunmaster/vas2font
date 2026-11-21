from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from vas2font.api.config import get_settings
from vas2font.api.db import sessions
from vas2font.api.errors import ApiError
from vas2font.api.font_routes import router as font_router
from vas2font.api.routes import router
from vas2font.api.template_routes import router as template_router
from vas2font.api.template_service import ensure_builtin_templates
from vas2font.api.upload_routes import router as upload_router


@asynccontextmanager
async def lifespan(application: FastAPI):
    async with sessions() as session:
        await ensure_builtin_templates(session)
    yield


app = FastAPI(
    title="VAS2Font",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)
app.include_router(router)
app.include_router(template_router)
app.include_router(upload_router)
app.include_router(font_router)


@app.exception_handler(ApiError)
def api_error_handler(request: Request, error: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={
            "code": error.code,
            "message": error.message,
            "details": error.details,
        },
    )


@app.exception_handler(RequestValidationError)
def validation_error_handler(
    request: Request, error: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "code": "validation_error",
            "message": "The request could not be validated",
            "details": jsonable_encoder(error.errors()),
        },
    )


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "font-src 'self' blob:; img-src 'self' data:; connect-src 'self'; "
        "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    )
    return response


frontend_dist = get_settings().frontend_dist.resolve()
if frontend_dist.is_dir():
    assets = frontend_dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{resource_path:path}", include_in_schema=False)
    def frontend(resource_path: str) -> FileResponse:
        if resource_path.startswith("api/"):
            raise ApiError(404, "endpoint_not_found", "The API endpoint was not found")
        candidate = (frontend_dist / resource_path).resolve()
        if (
            resource_path
            and candidate.is_relative_to(frontend_dist)
            and candidate.is_file()
        ):
            return FileResponse(candidate)
        return FileResponse(
            frontend_dist / "index.html", headers={"Cache-Control": "no-cache"}
        )
