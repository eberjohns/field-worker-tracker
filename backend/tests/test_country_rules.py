from decimal import Decimal

from fw.rules.country.ae import UAECountryPack
from fw.rules.country.sa import SaudiCountryPack


def test_uae_country_pack_rates_and_settings():
    pack = UAECountryPack()
    assert pack.country_code == "AE"
    assert pack.timezone_name == "Asia/Dubai"
    assert pack.currency == "AED"
    assert pack.weekend_days == (5, 6)
    assert pack.ot2_weekdays == (6,)

    # Test basic salary = 5000.00
    # 5000 / 208 * 1.25 = 30.04807... -> 30.05
    ot1 = pack.calculate_ot1_rate(Decimal("5000.00"))
    assert ot1 == Decimal("30.05")

    # 5000 / 208 * 1.50 = 36.05769... -> 36.06
    ot2 = pack.calculate_ot2_rate(Decimal("5000.00"))
    assert ot2 == Decimal("36.06")


def test_saudi_country_pack_rates_and_settings():
    pack = SaudiCountryPack()
    assert pack.country_code == "SA"
    assert pack.timezone_name == "Asia/Riyadh"
    assert pack.currency == "SAR"
    assert pack.weekend_days == (4, 5)
    assert pack.ot2_weekdays == (4,)

    ot1 = pack.calculate_ot1_rate(Decimal("5000.00"))
    assert ot1 == Decimal("30.05")

    ot2 = pack.calculate_ot2_rate(Decimal("5000.00"))
    assert ot2 == Decimal("36.06")
