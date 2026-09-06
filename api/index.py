from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from starlette.staticfiles import StaticFiles
import os

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html"
    )

@app.get("/about_us")
async def about_us(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="about.html"
    ) 

@app.get("/shop")
async def shop(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="shop.html"
    )

@app.get("/product")
async def shop(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="product.html"
    )

@app.get("/cart")
async def cart(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="cart.html"
    )

@app.get("/checkout")
async def cart(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="checkout.html"
    )

@app.get("/delivery")
async def cart(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="delivery.html"
    )

@app.get("/payment")
async def cart(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="payment.html"
    )

@app.get("/order_confirmation")
async def order_confirmation(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="order_confirmation.html"
    )