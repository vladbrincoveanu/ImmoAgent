#!/usr/bin/env python3
"""
Show available buyer profiles and how to use them
"""

from Application.buyer_profiles import print_all_profiles, print_profile_summary

def main():
    """Show all available buyer profiles"""
    print("🏠 Immo-Scouter Buyer Profiles")
    print("=" * 60)
    print("Choose a buyer profile to customize property scoring based on your needs.\n")
    
    print_all_profiles()
    
    print("\n" + "=" * 60)
    print("📖 HOW TO USE:")
    print("=" * 60)
    print("1. For main scraping:")
    print("   python run.py --buyer-profile=PROFILE_NAME")
    print("   python run.py --buyer-profile=diy_renovator --send-to-telegram")
    print()
    print("2. For Top5 report:")
    print("   python run_top5.py --buyer-profile=PROFILE_NAME")
    print("   python run_top5.py --buyer-profile=budget_buyer")
    print()
    print("3. Available profiles:")
    print("   • diy_renovator - Investment and renovation (DEFAULT)")
    print("   • default - Balanced scoring")
    print("   • growing_family - Space and schools priority")
    print("   • urban_professional - Location and lifestyle")
    print("   • eco_conscious - Energy efficiency focus")
    print("   • retiree - Comfort and accessibility")
    print("   • budget_buyer - Lowest price priority")
    print()
    print("4. Examples:")
    print("   • Investment property (default): python run.py")
    print("   • Looking for a family home: --buyer-profile=growing_family")
    print("   • First-time buyer: --buyer-profile=budget_buyer")
    print("   • Eco-friendly living: --buyer-profile=eco_conscious")
    print("   • Retirement home: --buyer-profile=retiree")
    print("   • Urban lifestyle: --buyer-profile=urban_professional")

if __name__ == "__main__":
    main() 