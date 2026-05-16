"""
Shared constants used across listing validation and filtering.
"""

RENTAL_KEYWORDS = [
    'unbefristet vermietet', 'unbefristet vermietete', 'unbefristet zum', 'unbefristet an',
    'vermietet', 'vermietete', 'vermietung', 'vermietungs', 'vermietbar',
    'bereits vermietet', 'aktuell vermietet', 'ist vermietet', 'wird vermietet',
    'miete', 'mieter', 'mietzins', 'mietvertrag', 'mietobjekt', 'mietwohnung',
    'mieteinnahmen', 'mietertrag', 'mietrendite',
    'rented', 'rental', 'tenant', 'tenancy', 'lease', 'leasing',
    'kat.a mietzins', 'kategorie a mietzins', 'kategorie-a mietzins',
    'mietzins kat.a', 'mietzins kategorie a', 'mietzins kategorie-a',
    'zum mietzins', 'an mietzins', 'mit mietzins', 'bei mietzins',
    'unbefristet', 'befristet', 'mietdauer', 'mietzeitraum'
]

PRICE_ON_REQUEST_KEYWORDS = [
    'preis auf anfrage', 'price on request', 'auf anfrage', 'on request',
    'preis nach vereinbarung', 'price by arrangement', 'nach vereinbarung',
    'preis n.v.', 'price n.v.', 'n.v.', 'n/a', 'na', 'tba', 'to be announced',
    'preis wird bekanntgegeben', 'price to be announced', 'wird bekanntgegeben'
]