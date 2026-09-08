from decimal import Decimal

import pytest

from app.selection.pricing import (
    FreightRule,
    PricingInput,
    calculate_billable_weight,
    calculate_freight,
    calculate_target_price,
)


def freight_rule(
    *,
    pricing_mode: str,
    per_kg_rate: Decimal | None = None,
    first_weight_kg: Decimal | None = None,
    first_weight_fee: Decimal | None = None,
    additional_weight_unit_kg: Decimal | None = None,
    additional_weight_fee: Decimal | None = None,
) -> FreightRule:
    return FreightRule(
        pricing_mode=pricing_mode,
        per_kg_rate=per_kg_rate,
        first_weight_kg=first_weight_kg,
        first_weight_fee=first_weight_fee,
        additional_weight_unit_kg=additional_weight_unit_kg,
        additional_weight_fee=additional_weight_fee,
    )


def test_target_price_uses_net_margin_and_commission():
    result = calculate_target_price(
        PricingInput(
            product_cost=Decimal("30"),
            domestic_shipping=Decimal("0"),
            international_shipping=Decimal("15"),
            exchange_rate=Decimal("1"),
            commission_rate=Decimal("0.15"),
            target_net_margin=Decimal("0.40"),
        )
    )

    assert result.target_price == Decimal("100.00")
    assert result.commission_amount == Decimal("15.00")
    assert result.net_profit_amount == Decimal("40.00")


def test_target_price_converts_product_domestic_and_international_costs():
    result = calculate_target_price(
        PricingInput(
            product_cost=Decimal("30"),
            domestic_shipping=Decimal("5"),
            international_shipping=Decimal("15"),
            exchange_rate=Decimal("0.20"),
            commission_rate=Decimal("0.15"),
            target_net_margin=Decimal("0.40"),
        )
    )

    assert result.converted_product_cost == Decimal("7.00")
    assert result.converted_international_shipping == Decimal("3.00")
    assert result.target_price == Decimal("22.22")


def test_target_price_rejects_non_positive_exchange_rate():
    data = PricingInput(
        product_cost=Decimal("30"),
        domestic_shipping=Decimal("0"),
        international_shipping=Decimal("15"),
        exchange_rate=Decimal("0"),
        commission_rate=Decimal("0.15"),
        target_net_margin=Decimal("0.40"),
    )

    with pytest.raises(ValueError, match="^汇率必须大于 0$"):
        calculate_target_price(data)


@pytest.mark.parametrize(
    ("commission_rate", "target_net_margin"),
    [("0.60", "0.40"), ("0.80", "0.30"), ("1", "0")],
)
def test_target_price_rejects_commission_and_margin_total_of_one_or_more(
    commission_rate: str,
    target_net_margin: str,
):
    data = PricingInput(
        product_cost=Decimal("30"),
        domestic_shipping=Decimal("0"),
        international_shipping=Decimal("15"),
        exchange_rate=Decimal("1"),
        commission_rate=Decimal(commission_rate),
        target_net_margin=Decimal(target_net_margin),
    )

    with pytest.raises(ValueError, match="^平台佣金率与净利润率之和必须小于 100%$"):
        calculate_target_price(data)


def test_billable_weight_takes_larger_of_actual_and_volume():
    weight = calculate_billable_weight(
        Decimal("0.10"),
        Decimal("60"),
        Decimal("40"),
        Decimal("30"),
        Decimal("6000"),
        Decimal("0"),
    )

    assert weight == Decimal("12")


def test_billable_weight_applies_minimum_weight():
    weight = calculate_billable_weight(
        Decimal("0.10"),
        Decimal("10"),
        Decimal("10"),
        Decimal("10"),
        Decimal("6000"),
        Decimal("0.50"),
    )

    assert weight == Decimal("0.50")


@pytest.mark.parametrize("volume_divisor", [Decimal("0"), Decimal("-6000")])
def test_billable_weight_rejects_non_positive_volume_divisor(volume_divisor: Decimal):
    with pytest.raises(ValueError, match="^体积重除数必须大于 0$"):
        calculate_billable_weight(
            Decimal("0.10"),
            Decimal("10"),
            Decimal("10"),
            Decimal("10"),
            volume_divisor,
            Decimal("0"),
        )


def test_per_kg_freight_uses_decimal_money_rounding():
    fee = calculate_freight(
        Decimal("1.0005"),
        freight_rule(pricing_mode="per_kg", per_kg_rate=Decimal("10")),
    )

    assert fee == Decimal("10.01")


def test_first_additional_freight_charges_first_weight_only_at_boundary():
    fee = calculate_freight(
        Decimal("1"),
        freight_rule(
            pricing_mode="first_additional",
            first_weight_kg=Decimal("1"),
            first_weight_fee=Decimal("20"),
            additional_weight_unit_kg=Decimal("0.5"),
            additional_weight_fee=Decimal("6"),
        ),
    )

    assert fee == Decimal("20.00")


@pytest.mark.parametrize(
    ("weight_kg", "expected"),
    [("1.01", "26.00"), ("1.50", "26.00"), ("1.51", "32.00")],
)
def test_first_additional_freight_rounds_additional_units_up(
    weight_kg: str,
    expected: str,
):
    fee = calculate_freight(
        Decimal(weight_kg),
        freight_rule(
            pricing_mode="first_additional",
            first_weight_kg=Decimal("1"),
            first_weight_fee=Decimal("20"),
            additional_weight_unit_kg=Decimal("0.5"),
            additional_weight_fee=Decimal("6"),
        ),
    )

    assert fee == Decimal(expected)


def test_first_additional_freight_rejects_non_positive_additional_unit():
    rule = freight_rule(
        pricing_mode="first_additional",
        first_weight_kg=Decimal("1"),
        first_weight_fee=Decimal("20"),
        additional_weight_unit_kg=Decimal("0"),
        additional_weight_fee=Decimal("6"),
    )

    with pytest.raises(ValueError, match="^续重单位必须大于 0$"):
        calculate_freight(Decimal("2"), rule)


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("actual_weight_kg", Decimal("NaN")),
        ("length_cm", Decimal("Infinity")),
        ("width_cm", Decimal("-Infinity")),
        ("height_cm", Decimal("NaN")),
        ("volume_divisor", Decimal("Infinity")),
        ("minimum_weight_kg", Decimal("-Infinity")),
    ],
)
def test_billable_weight_rejects_non_finite_decimal_fields(
    field_name: str,
    invalid_value: Decimal,
):
    values = {
        "actual_weight_kg": Decimal("1"),
        "length_cm": Decimal("10"),
        "width_cm": Decimal("10"),
        "height_cm": Decimal("10"),
        "volume_divisor": Decimal("6000"),
        "minimum_weight_kg": Decimal("0"),
    }
    values[field_name] = invalid_value

    with pytest.raises(ValueError, match="必须是有限数值"):
        calculate_billable_weight(**values)


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("weight_kg", Decimal("NaN")),
        ("per_kg_rate", Decimal("Infinity")),
        ("first_weight_kg", Decimal("-Infinity")),
        ("first_weight_fee", Decimal("NaN")),
        ("additional_weight_unit_kg", Decimal("Infinity")),
        ("additional_weight_fee", Decimal("-Infinity")),
    ],
)
def test_freight_rejects_non_finite_decimal_fields(
    field_name: str,
    invalid_value: Decimal,
):
    values = {
        "weight_kg": Decimal("2"),
        "per_kg_rate": Decimal("10"),
        "first_weight_kg": Decimal("1"),
        "first_weight_fee": Decimal("20"),
        "additional_weight_unit_kg": Decimal("0.5"),
        "additional_weight_fee": Decimal("6"),
    }
    values[field_name] = invalid_value
    weight_kg = values.pop("weight_kg")
    rule = FreightRule(pricing_mode="first_additional", **values)

    with pytest.raises(ValueError, match="必须是有限数值"):
        calculate_freight(weight_kg, rule)


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("product_cost", Decimal("NaN")),
        ("domestic_shipping", Decimal("Infinity")),
        ("international_shipping", Decimal("-Infinity")),
        ("exchange_rate", Decimal("NaN")),
        ("commission_rate", Decimal("Infinity")),
        ("target_net_margin", Decimal("-Infinity")),
    ],
)
def test_target_price_rejects_non_finite_decimal_fields(
    field_name: str,
    invalid_value: Decimal,
):
    values = {
        "product_cost": Decimal("30"),
        "domestic_shipping": Decimal("0"),
        "international_shipping": Decimal("15"),
        "exchange_rate": Decimal("1"),
        "commission_rate": Decimal("0.15"),
        "target_net_margin": Decimal("0.40"),
    }
    values[field_name] = invalid_value

    with pytest.raises(ValueError, match="必须是有限数值"):
        calculate_target_price(PricingInput(**values))
