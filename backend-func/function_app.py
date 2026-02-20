"""Azure Functions v2 entrypoint that proxies all routes to the FastAPI app."""

import azure.functions as func

from app.main import app as fastapi_app

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)
asgi_middleware = func.AsgiMiddleware(fastapi_app)


@app.function_name(name="api")
@app.route(
    route="{*route}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
async def api(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    """Forward every HTTP request to the FastAPI ASGI application."""

    return await asgi_middleware.handle_async(req, context)
