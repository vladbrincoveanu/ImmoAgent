# Immo-Scouter Domain Glossary

## Core Domain Terms

| Term | Definition |
|------|------------|
| **Listing** | Property advertisement from willhaben, immo_kurier, or derstandard. Stored as MongoDB document. |
| **Buyer Profile** | Weight distribution for scoring criteria. 8 personas: default, owner_occupier, diy_renovator, growing_family, urban_professional, eco_conscious, retiree, budget_buyer. |
| **GLOBAL_VALIDATION** | Single source of truth for listing validation thresholds: min_price_per_m2 (€1k), max_price_per_m2 (€20k). Only price_per_m2 is validated. |
| **NORMALIZATION_RANGES** | Min/max values for scoring criteria normalization. Defines "ideal" (score 100) and "acceptable worst" (score 0) for each criterion. |
| **Content Fingerprint** | MD5 hash of title+area_m2+rooms+bezirk+source_enum. Used for deduplication of same-listing-different-URL. |
| **Bezirk** | Vienna district code (1010-1230). |
| **HWB Value** | Heizwarmbedarf - Energy required per m²/year (kWh/m²/Jahr). Range: 20 (A/A+) to 150 (F/G). |

## Architecture Terms

| Term | Definition |
|------|------------|
| **Module** | Anything with an interface and implementation: function, class, package, slice. |
| **Seam** | Where an interface lives — place behaviour can be altered without editing in place. |
| **Depth** | Leverage at the interface: lots of behaviour behind a small interface. |
| **Shallow** | Interface nearly as complex as the implementation. |

## Validation Rules

- Missing price/area → passes (price-on-request listings exist)
- price_per_m2 < €2,000 or > €20,000 → fails
- price_total < €50,000 → fails
- area_m2 < 30 → fails
- Rental keywords in title/description → fails
- Price-on-request keywords → fails
