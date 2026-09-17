# Real catalog data with real product photos (static/images/productpictures/)
# and real prices. Every pack/size Redbased sells is its own product listing —
# this farm only sells palm oil, so there's no separate brand/category tree,
# just one size each. Run with:
#   python scripts/seed_products.py
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from database import SessionLocal, init_db
from models.product import Product, ProductVariant

IMG_DIR = "images/productpictures/"

# Default stock quantity for a freshly seeded product. Placeholder until real
# inventory counts are wired up — update per product as stock is tracked.
DEFAULT_STOCK_QTY = 25

PALM_OIL_SPECS = {
    "Extraction": "Cold-pressed",
    # "Colour": "Deep red (high beta-carotene)",
    "Shelf Life": "18 months (sealed)",
    "Certification": "NAFDAC Approved",
}

PALM_OIL_NUTRITION = [
    {"label": "Energy", "value": "900kcal", "percent": 85},
    {"label": "Total Fat", "value": "100g", "percent": 60},
    {"label": "Saturated Fats", "value": "50g", "percent": 40},
    {"label": "Monounsaturated Fats", "value": "37g", "percent": 40},
    {"label": "Polyunsaturated Fats", "value": "9g", "percent": 40},
    {"label": "Vitamin E", "value": "15-25mg", "percent": 40},
]


def _images(*filenames):
    return [IMG_DIR + name for name in filenames]


PRODUCTS = [
    {
        "slug": "redbased-palm-oil-2-5ml",
        "name": "Redbased Palm Oil - 2.5ml",
        "size_label": "2.5ml",
        "price": 500,
        "images": _images("single-2-5ml.jpg", "single-2-5ml-alt.jpg"),
        "is_featured": True,
        "is_bestseller": False,
    },
    {
        "slug": "redbased-palm-oil-400ml",
        "name": "Redbased Palm Oil - 400ml",
        "size_label": "400ml",
        "price": 4300,
        "images": _images("single-400ml.jpg", "single-400ml-alt.jpg"),
        "is_featured": True,
        "is_bestseller": True,
    },
    {
        "slug": "redbased-palm-oil-500ml",
        "name": "Redbased Palm Oil - 500ml",
        "size_label": "500ml",
        "price": 5000,
        "images": _images("single-500ml.jpg", "single-500ml-alt.jpg", "single-500ml-alt2.jpg"),
        "is_featured": True,
        "is_bestseller": True,
    },
    {
        "slug": "redbased-palm-oil-2-5l",
        "name": "Redbased Palm Oil - 2.5L",
        "size_label": "2.5L",
        "price": 12500,
        "images": _images("single-2-5l.jpg", "single-2-5l-alt.jpg"),
        "is_featured": True,
        "is_bestseller": False,
    },
    {
        "slug": "redbased-palm-oil-4l",
        "name": "Redbased Palm Oil - 4L",
        "size_label": "4L",
        "price": 15000,
        "images": _images("single-4l.jpg", "single-4l-alt.jpg"),
        "is_featured": False,
        "is_bestseller": False,
    },
    {
        "slug": "redbased-palm-oil-5l",
        "name": "Redbased Palm Oil - 5L",
        "size_label": "5L",
        "price": 20000,
        "images": _images("single-5l.jpg", "single-5l-alt.jpg"),
        "is_featured": False,
        "is_bestseller": False,
    },
    {
        "slug": "redbased-palm-oil-25l",
        "name": "Redbased Palm Oil - 25L",
        "size_label": "25L",
        "price": 90000,
        "images": _images("single-25l.jpg", "single-25l-alt.jpg"),
        "is_featured": False,
        "is_bestseller": False,
    },
    {
        "slug": "redbased-palm-oil-30l",
        "name": "Redbased Palm Oil - 30L",
        "size_label": "30L",
        "price": 120000,
        "images": _images("single-30l.jpg", "single-30l-alt.jpg"),
        "is_featured": False,
        "is_bestseller": False,
    },
    {
        "slug": "redbased-palm-oil-sachet-roll-100ml",
        "name": "Redbased Palm Oil - Sachet Roll (100ml x6)",
        "size_label": "Sachet Roll - 100ml (6 sachets)",
        "price": 1200,
        "images": _images("sachet-roll-100ml.jpg", "sachet-roll-100ml-alt.jpg"),
        "is_featured": True,
        "is_bestseller": True,
    },
    {
        "slug": "redbased-palm-oil-carton-400ml-8pack",
        "name": "Redbased Palm Oil - Carton (400ml x8)",
        "size_label": "Carton - 400ml (8 bottles)",
        "price": 45000,
        "images": _images("carton-400ml-8pack.jpg", "carton-400ml-8pack-alt.jpg"),
        "is_featured": False,
        "is_bestseller": False,
    },
    {
        "slug": "redbased-palm-oil-carton-400ml-12pack",
        "name": "Redbased Palm Oil - Carton (400ml x12)",
        "size_label": "Carton - 400ml (12 bottles)",
        "price": 60000,
        "images": _images("carton-400ml-12pack.jpg", "carton-400ml-12pack-alt.jpg"),
        "is_featured": True,
        "is_bestseller": True,
    },
    {
        "slug": "redbased-palm-oil-carton-500ml-10pack",
        "name": "Redbased Palm Oil - Carton (500ml x10)",
        "size_label": "Carton - 500ml (10 bottles)",
        "price": 50000,
        "images": _images("carton-500ml-10pack.jpg", "carton-500ml-10pack-alt.jpg", "carton-500ml-10pack-alt2.jpg"),
        "is_featured": False,
        "is_bestseller": False,
    },
]


def seed():
    init_db()
    db = SessionLocal()
    try:
        valid_slugs = {entry["slug"] for entry in PRODUCTS}
        stale_products = db.query(Product).filter(~Product.slug.in_(valid_slugs)).all()
        removed = len(stale_products)
        for product in stale_products:
            db.delete(product)

        created, updated = 0, 0
        for entry in PRODUCTS:
            images = entry["images"]
            product = db.query(Product).filter_by(slug=entry["slug"]).one_or_none()

            fields = {
                "slug": entry["slug"],
                "name": entry["name"],
                "category": "Palm Oil",
                "description": (
                    "Cold-pressed red palm oil straight from our farm, packed fresh — "
                    f"this listing is the {entry['size_label']} pack."
                ),
                "specs": PALM_OIL_SPECS,
                "nutrition_facts": PALM_OIL_NUTRITION,
                "image_primary": images[0],
                "image_gallery": images,
                "badge": None,
                "rating_score": 0,
                "rating_count": 0,
                "is_featured": entry["is_featured"],
                "is_bestseller": entry["is_bestseller"],
            }

            if product is None:
                product = Product(**fields)
                db.add(product)
                created += 1
            else:
                for key, value in fields.items():
                    setattr(product, key, value)
                updated += 1

            product.variants = [
                ProductVariant(
                    size_label=entry["size_label"],
                    price=entry["price"],
                    stock_qty=DEFAULT_STOCK_QTY,
                    image=images[0],
                    image_gallery=images,
                )
            ]

        db.commit()
        print(f"Seed complete: {created} created, {updated} updated, {removed} stale products removed.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
