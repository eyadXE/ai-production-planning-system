"""Catalog products — the real Ousus product lines from ousus.com."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from finalproject.db.models import Product

CATALOGUE_BASE = "/catalogs"

PRODUCTS = [
    # Carbon Steel Products
    ("Carbon Steel", "Railings", "SHS-post railings with flat-bar or mesh infill, any run length, shop painted in any RAL.", "railings.jpg", "railing", "metre"),
    ("Carbon Steel", "Staircases", "Straight steel staircases with chequer-plate treads; landings and balustrades quoted separately.", "carbon.png", "flight", "flight"),
    ("Carbon Steel", "Ladders & Rungs", "Caged access ladders and individual rungs for plant and maintenance access.", "workshop.png", "caged_ladder", "count"),
    ("Carbon Steel", "Walkways", "Elevated steel walkways with anti-slip walking surfaces.", "about-1.png", None, "m2"),
    ("Carbon Steel", "Trench Covers", "Removable chequer-plate trench covers for utilities and drainage.", "about-1.png", "floor_plate_area", "m2"),
    ("Carbon Steel", "Fences", "Steel boundary and security fencing, mesh or solid infill.", "carbon.png", "railing", "metre"),
    ("Carbon Steel", "Gates", "Single or double swing/sliding gates with SHS frames.", "carbon.png", "gate_double", "count"),
    ("Carbon Steel", "Technical Rooms", "Prefabricated steel technical rooms and enclosures.", "workshop.png", None, "count"),
    ("Carbon Steel", "Car Sheds", "Freestanding steel car sheds and parking covers.", "hero.jpg", None, "m2"),
    ("Carbon Steel", "Claddings", "Steel wall and facade cladding systems.", "about-2.png", None, "m2"),
    # Structural Steel Works
    ("Structural Steel", "Warehouse Structures", "Complete structural steel warehouses, primary and secondary framing.", "hero.jpg", None, "m2"),
    ("Structural Steel", "Heavy-Duty Staircases", "Industrial staircases for heavy traffic and plant environments.", "workshop.png", "flight", "flight"),
    ("Structural Steel", "Signal Light Posts", "Galvanised steel posts for traffic and site signalling.", "workshop.png", None, "count"),
    # Aluminium Decorative
    ("Aluminium Decorative", "Decorative Panels / Mushrabiya", "Laser-cut decorative screens and mashrabiya facades.", "about-2.png", None, "m2"),
    ("Aluminium Decorative", "Sandtrap Louvers", "Sand-trap louvre systems for desert-climate ventilation intakes.", "about-2.png", None, "m2"),
    ("Aluminium Decorative", "Ship Ladders", "Steep-space-saving aluminium ship ladders.", "about-1.png", None, "count"),
    ("Aluminium Decorative", "Aluminium Partitions", "Lightweight aluminium partitioning systems.", "about-2.png", None, "m2"),
    # Stainless Steel
    ("Stainless Steel", "SS Railings", "Polished stainless balustrades for premium interiors and pools.", "about-2.png", "railing", "metre"),
    ("Stainless Steel", "Claddings", "Stainless cladding for columns, lifts and feature walls.", "about-2.png", None, "m2"),
    ("Stainless Steel", "Gratings", "Stainless gratings for drainage and walkway surfaces.", "about-1.png", None, "m2"),
    ("Stainless Steel", "Green Walls", "Stainless green-wall support structures.", "about-1.png", None, "m2"),
    ("Stainless Steel", "Water Tank Ladders", "Corrosion-proof ladder sets for water tanks.", "workshop.png", "caged_ladder", "count"),
    ("Stainless Steel", "Roof Walkways", "Stainless roof walkway systems with non-slip surfaces.", "about-1.png", None, "m2"),
    ("Stainless Steel", "Technical Room Louvers", "Stainless louvres for technical rooms and plant areas.", "about-2.png", None, "m2"),
]

CATALOGUES = [
    ("Carbon Steel Products catalogue", f"{CATALOGUE_BASE}/carbon_steel.pdf"),
    ("Structural Steel Works catalogue", f"{CATALOGUE_BASE}/structural_steel.pdf"),
    ("Aluminium Decorative catalogue", f"{CATALOGUE_BASE}/auminum_decorative.pdf"),
    ("Stainless Steel catalogue", f"{CATALOGUE_BASE}/stainless_steel.pdf"),
]


CATEGORY_IMAGE = {
    "Carbon Steel": "/images/carbon.png",
    "Structural Steel": "/images/structural.jpg",
    "Aluminium Decorative": "/images/about-2.png",
    "Stainless Steel": "/images/stainless.jpg",
}


def seed_products(session: Session) -> int:
    if session.scalar(select(Product).limit(1)):
        return 0  # already seeded
    for category, name, desc, img, kind, unit in PRODUCTS:
        image = CATEGORY_IMAGE.get(category) or f"/images/{img}"
        session.add(Product(
            category=category, name=name, description=desc,
            image=image, est_kind=kind, unit=unit,
        ))
    session.commit()
    return len(PRODUCTS)
