from fastapi import APIRouter, Request

from utils.templates import templates

router = APIRouter()


@router.get("/")
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html"
    )


@router.get("/about_us")
async def about_us(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="about.html"
    )


@router.get("/shop")
async def shop(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="shop.html"
    )


@router.get("/product")
async def product(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="product.html"
    )


@router.get("/cart")
async def cart(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="cart.html"
    )


@router.get("/checkout")
async def checkout(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="checkout.html"
    )


@router.get("/delivery")
async def delivery(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="delivery.html"
    )


@router.get("/payment")
async def payment(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="payment.html"
    )


@router.get("/order_confirmation")
async def order_confirmation(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="order_confirmation.html"
    )
