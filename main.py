from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from starlette.staticfiles import StaticFiles

app = FastAPI()

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html"
    )