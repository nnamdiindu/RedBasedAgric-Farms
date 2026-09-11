import json
import math

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database import get_db
from models.product import Product
from utils.formatting import format_naira
from utils.query_helpers import make_query_builder
from utils.templates import templates

router = APIRouter()

CATEGORIES = ["Palm Oil"]
PAGE_SIZE = 8


def _card(product: Product) -> dict:
    return {
        "slug": product.slug,
        "name": product.name,
        "category": product.category,
        "image": product.image_primary,
        "badge": product.badge,
        "rating_count": product.rating_count,
        "in_stock": product.in_stock,
        "price_display": format_naira(product.min_price) if product.min_price is not None else "",
    }


@router.get("/")
async def index(request: Request, db: Session = Depends(get_db)):
    featured = (
        db.query(Product)
        .filter(Product.is_active.is_(True), Product.is_featured.is_(True))
        .limit(6)
        .all()
    )
    bestsellers = (
        db.query(Product)
        .filter(Product.is_active.is_(True), Product.is_bestseller.is_(True))
        .limit(4)
        .all()
    )
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "featured_products": [_card(p) for p in featured],
            "bestseller_products": [_card(p) for p in bestsellers],
        },
    )


@router.get("/shop")
async def shop(
    request: Request,
    db: Session = Depends(get_db),
    category: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    in_stock: bool = False,
    q: str | None = None,
    page: int = 1,
):
    query = db.query(Product).filter(Product.is_active.is_(True))

    if category in CATEGORIES:
        query = query.filter(Product.category == category)
    else:
        category = None

    if q:
        like = f"%{q}%"
        query = query.filter(or_(Product.name.ilike(like), Product.description.ilike(like)))

    products = query.all()

    if min_price is not None:
        products = [p for p in products if p.min_price is not None and p.min_price >= min_price]
    if max_price is not None:
        products = [p for p in products if p.min_price is not None and p.min_price <= max_price]
    if in_stock:
        products = [p for p in products if p.in_stock]

    total_count = db.query(Product).filter(Product.is_active.is_(True)).count()
    category_counts = {
        cat: db.query(Product).filter(Product.is_active.is_(True), Product.category == cat).count()
        for cat in CATEGORIES
    }

    result_count = len(products)
    total_pages = max(1, math.ceil(result_count / PAGE_SIZE))
    page = min(max(page, 1), total_pages)
    start = (page - 1) * PAGE_SIZE
    page_products = products[start:start + PAGE_SIZE]

    build_query = make_query_builder({
        "category": category,
        "q": q,
        "min_price": min_price,
        "max_price": max_price,
        "in_stock": in_stock,
    })

    return templates.TemplateResponse(
        request=request,
        name="shop.html",
        context={
            "products": [_card(p) for p in page_products],
            "categories": CATEGORIES,
            "category_counts": category_counts,
            "total_count": total_count,
            "result_count": result_count,
            "selected_category": category,
            "min_price": min_price if min_price is not None else 0,
            "max_price": max_price if max_price is not None else 25000,
            "in_stock": in_stock,
            "search_query": q or "",
            "page": page,
            "total_pages": total_pages,
            "build_query": build_query,
        },
    )


@router.get("/product/{slug}")
async def product_detail(request: Request, slug: str, db: Session = Depends(get_db)):
    product = (
        db.query(Product)
        .filter(Product.slug == slug, Product.is_active.is_(True))
        .one_or_none()
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    variants = []
    for variant in product.variants:
        raw_images = variant.image_gallery or ([variant.image] if variant.image else [])
        resolved_images = [str(request.url_for("static", path=path)) for path in raw_images]
        variants.append({
            "id": variant.id,
            "size_label": variant.size_label,
            "price_display": format_naira(variant.price),
            "in_stock": variant.in_stock,
            "raw_images": raw_images,
            "images_json": json.dumps(resolved_images),
        })

    gallery = (
        variants[0]["raw_images"] if variants and variants[0]["raw_images"]
        else (product.image_gallery or [product.image_primary])
    )

    return templates.TemplateResponse(
        request=request,
        name="product.html",
        context={
            "product": product,
            "variants": variants,
            "gallery": gallery,
            "price_display": format_naira(product.min_price) if product.min_price is not None else "",
        },
    )
