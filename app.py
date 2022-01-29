import asyncio

from fastapi import FastAPI
from uvicorn import Config, Server
from routers import files, users, companies


app = FastAPI()


app.include_router(files.router)
app.include_router(users.router)
app.include_router(companies.router)


@app.get("/")
async def main_page():
    return dict(message="Welcome to main page")


if __name__ == "__main__":
    loop_main = asyncio.new_event_loop()
    config_server = Config(app=app, loop=loop_main, host='localhost', port=3000)
    server = Server(config_server)
    loop_main.run_until_complete(server.serve())
