import asyncio

from fastapi import FastAPI
from uvicorn import Config, Server
from routers import files, users, companies
from fastapi_jwt_auth.exceptions import AuthJWTException
from fastapi.requests import Request
from fastapi.responses import JSONResponse
import config

app = FastAPI()


app.include_router(files.router)
app.include_router(users.router)
app.include_router(companies.router)


@app.get("/")
async def main_page():
    return dict(message="Welcome to main page")


@app.exception_handler(AuthJWTException)
def authjwt_exception_handler(request: Request, exc: AuthJWTException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message}
    )


if __name__ == "__main__":
    loop_main = asyncio.new_event_loop()
    config_server = Config(app=app, loop=loop_main, host=config.server_host, port=config.port)
    server = Server(config_server)
    loop_main.run_until_complete(server.serve())
