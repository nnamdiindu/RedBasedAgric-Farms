from fastapi import APIRouter, Request

from utils.templates import templates

router = APIRouter()


@router.get("/about_us")
async def about_us(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="about.html"
    )


