from io import BytesIO

import pytest

from app.importers.tabular import ImportValidationError, parse_tabular_upload


def test_parse_tabular_upload_normalizes_required_columns_from_csv():
    content = "SKU,Date,Units Sold,Sales Amount\nSKU-001,2026-01-01,10,300.50\n"

    rows = parse_tabular_upload(
        filename="sales.csv",
        content=content.encode("utf-8"),
        required_columns={"SKU": "sku", "Date": "date", "Units Sold": "units_sold"},
        optional_columns={"Sales Amount": "sales_amount"},
    )

    assert rows == [
        {
            "sku": "SKU-001",
            "date": "2026-01-01",
            "units_sold": 10,
            "sales_amount": 300.5,
        }
    ]


def test_parse_tabular_upload_rejects_missing_required_columns():
    content = "SKU,Units Sold\nSKU-001,10\n"

    with pytest.raises(ImportValidationError) as exc:
        parse_tabular_upload(
            filename="sales.csv",
            content=content.encode("utf-8"),
            required_columns={"SKU": "sku", "Date": "date"},
            optional_columns={},
        )

    assert "Date" in str(exc.value)


def test_parse_tabular_upload_reads_excel_uploads():
    import pandas as pd

    buffer = BytesIO()
    pd.DataFrame([{"SKU": "SKU-001", "Date": "2026-01-01"}]).to_excel(buffer, index=False)

    rows = parse_tabular_upload(
        filename="sku.xlsx",
        content=buffer.getvalue(),
        required_columns={"SKU": "sku", "Date": "date"},
        optional_columns={},
    )

    assert rows == [{"sku": "SKU-001", "date": "2026-01-01"}]
