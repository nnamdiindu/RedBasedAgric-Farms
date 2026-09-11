import os

from dotenv import load_dotenv
from fastapi import FastAPI
from starlette.staticfiles import StaticFiles

from routers import contact, pages

load_dotenv()

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

app.include_router(pages.router)
app.include_router(contact.router)
