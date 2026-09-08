from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from typing import Literal


MONEY_UNIT = Decimal("0.01")


@dataclass(frozen=True)
class FreightRule:
    pricing_mode: Literal["per_kg", "first_additional"]
    per_kg_rate: Decimal | None
    first_weight_kg: Decimal | None
    first_weight_fee: Decimal | None
    additional_weight_unit_kg: Decimal | None
    additional_weight_fee: Decimal | None


@dataclass(frozen=True)
class PricingInput:
    product_cost: Decimal
    domestic_shipping: Decimal
    international_shipping: Decimal
    exchange_rate: Decimal
    commission_rate: Decimal
    target_net_margin: Decimal


@dataclass(frozen=True)
class PricingResult:
    converted_product_cost: Decimal
    converted_international_shipping: Decimal
    target_price: Decimal
    commission_amount: Decimal
    net_profit_amount: Decimal


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_UNIT, rounding=ROUND_HALF_UP)


def calculate_billable_weight(
    actual_weight_kg: Decimal,
    length_cm: Decimal,
    width_cm: Decimal,
    height_cm: Decimal,
    volume_divisor: Decimal,
    minimum_weight_kg: Decimal,
) -> Decimal:
    _require_finite(actual_weight_kg, "实际重量")
    _require_finite(length_cm, "长度")
    _require_finite(width_cm, "宽度")
    _require_finite(height_cm, "高度")
    _require_finite(volume_divisor, "体积重除数")
    _require_finite(minimum_weight_kg, "最低计费重量")

    if volume_divisor <= 0:
        raise ValueError("体积重除数必须大于 0")

    _require_non_negative(actual_weight_kg, "实际重量")
    _require_non_negative(length_cm, "长度")
    _require_non_negative(width_cm, "宽度")
    _require_non_negative(height_cm, "高度")
    _require_non_negative(minimum_weight_kg, "最低计费重量")

    volumetric_weight_kg = length_cm * width_cm * height_cm / volume_divisor
    return max(actual_weight_kg, volumetric_weight_kg, minimum_weight_kg)


def calculate_freight(weight_kg: Decimal, template: FreightRule) -> Decimal:
    _require_finite(weight_kg, "计费重量")
    _require_optional_finite(template.per_kg_rate, "每公斤价格")
    _require_optional_finite(template.first_weight_kg, "首重")
    _require_optional_finite(template.first_weight_fee, "首重价格")
    _require_optional_finite(template.additional_weight_unit_kg, "续重单位")
    _require_optional_finite(template.additional_weight_fee, "续重价格")

    _require_non_negative(weight_kg, "计费重量")

    if template.pricing_mode == "per_kg":
        per_kg_rate = _required_value(template.per_kg_rate, "每公斤价格")
        _require_non_negative(per_kg_rate, "每公斤价格")
        return money(weight_kg * per_kg_rate)

    if template.pricing_mode == "first_additional":
        first_weight_kg = _required_value(template.first_weight_kg, "首重")
        first_weight_fee = _required_value(template.first_weight_fee, "首重价格")
        additional_unit = _required_value(template.additional_weight_unit_kg, "续重单位")
        additional_fee = _required_value(template.additional_weight_fee, "续重价格")

        if first_weight_kg <= 0:
            raise ValueError("首重必须大于 0")
        if additional_unit <= 0:
            raise ValueError("续重单位必须大于 0")
        _require_non_negative(first_weight_fee, "首重价格")
        _require_non_negative(additional_fee, "续重价格")

        if weight_kg <= first_weight_kg:
            return money(first_weight_fee)

        additional_units = ((weight_kg - first_weight_kg) / additional_unit).to_integral_value(
            rounding=ROUND_CEILING
        )
        return money(first_weight_fee + additional_units * additional_fee)

    raise ValueError("运费计价模式必须是 per_kg 或 first_additional")


def calculate_target_price(input: PricingInput) -> PricingResult:
    _require_finite(input.product_cost, "商品价格")
    _require_finite(input.domestic_shipping, "国内运费")
    _require_finite(input.international_shipping, "国际运费")
    _require_finite(input.exchange_rate, "汇率")
    _require_finite(input.commission_rate, "平台佣金率")
    _require_finite(input.target_net_margin, "净利润率")

    _require_non_negative(input.product_cost, "商品价格")
    _require_non_negative(input.domestic_shipping, "国内运费")
    _require_non_negative(input.international_shipping, "国际运费")
    if input.exchange_rate <= 0:
        raise ValueError("汇率必须大于 0")
    _require_rate(input.commission_rate, "平台佣金率")
    _require_rate(input.target_net_margin, "净利润率")

    denominator = Decimal("1") - input.commission_rate - input.target_net_margin
    if denominator <= 0:
        raise ValueError("平台佣金率与净利润率之和必须小于 100%")

    # 商品价格与国内运费同属商品成本；国际运费单独换算，便于结果追溯。
    converted_product_cost = money(
        (input.product_cost + input.domestic_shipping) * input.exchange_rate
    )
    converted_international_shipping = money(
        input.international_shipping * input.exchange_rate
    )
    target_price = money(
        (converted_product_cost + converted_international_shipping) / denominator
    )

    return PricingResult(
        converted_product_cost=converted_product_cost,
        converted_international_shipping=converted_international_shipping,
        target_price=target_price,
        commission_amount=money(target_price * input.commission_rate),
        net_profit_amount=money(target_price * input.target_net_margin),
    )


def _required_value(value: Decimal | None, name: str) -> Decimal:
    if value is None:
        raise ValueError(f"{name}不能为空")
    return value


def _require_finite(value: Decimal, name: str) -> None:
    if not value.is_finite():
        raise ValueError(f"{name}必须是有限数值")


def _require_optional_finite(value: Decimal | None, name: str) -> None:
    if value is not None:
        _require_finite(value, name)


def _require_non_negative(value: Decimal, name: str) -> None:
    if value < 0:
        raise ValueError(f"{name}不能小于 0")


def _require_rate(value: Decimal, name: str) -> None:
    if value < 0:
        raise ValueError(f"{name}必须大于等于 0 且小于 100%")
