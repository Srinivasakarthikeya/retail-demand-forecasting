"""Assumed Indian retail prices (INR per unit) and department for each product family.

The Favorita data has units only. These prices are illustrative assumptions used to show
sales value in rupees; change them here and restart the API.
"""
FAMILY_PRICES = {
    # family: (department, price_inr)
    "GROCERY I": ("Food & Grocery", 80), "GROCERY II": ("Food & Grocery", 90),
    "PRODUCE": ("Food & Grocery", 40), "DAIRY": ("Food & Grocery", 55),
    "BREAD/BAKERY": ("Food & Grocery", 45), "DELI": ("Food & Grocery", 180),
    "EGGS": ("Food & Grocery", 90), "FROZEN FOODS": ("Food & Grocery", 220),
    "MEATS": ("Food & Grocery", 350), "POULTRY": ("Food & Grocery", 250),
    "PREPARED FOODS": ("Food & Grocery", 150), "SEAFOOD": ("Food & Grocery", 500),
    "BEVERAGES": ("Beverages", 60), "LIQUOR,WINE,BEER": ("Beverages", 450),
    "CLEANING": ("Home & Living", 120), "HOME CARE": ("Home & Living", 150),
    "HOME AND KITCHEN I": ("Home & Living", 400), "HOME AND KITCHEN II": ("Home & Living", 350),
    "HOME APPLIANCES": ("Home & Living", 2500), "LAWN AND GARDEN": ("Home & Living", 300),
    "HARDWARE": ("Home & Living", 300), "AUTOMOTIVE": ("Home & Living", 450),
    "BEAUTY": ("Beauty & Personal Care", 300), "PERSONAL CARE": ("Beauty & Personal Care", 150),
    "BABY CARE": ("Beauty & Personal Care", 350),
    "LADIESWEAR": ("Apparel", 700), "LINGERIE": ("Apparel", 400),
    "BOOKS": ("Leisure & Stationery", 250), "MAGAZINES": ("Leisure & Stationery", 100),
    "CELEBRATION": ("Leisure & Stationery", 200), "PLAYERS AND ELECTRONICS": ("Leisure & Stationery", 1500),
    "SCHOOL AND OFFICE SUPPLIES": ("Leisure & Stationery", 60), "PET SUPPLIES": ("Leisure & Stationery", 300),
}
DEFAULT = ("Other", 100)
