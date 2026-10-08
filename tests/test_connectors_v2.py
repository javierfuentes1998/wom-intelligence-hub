import io
from app.connectors import CSVConnector,ExcelConnector,parse_date,parse_decimal,validate_rows
def test_csv_semicolon_and_encoding():
    p=CSVConnector().preview("fecha;importe\n01/02/2026;12,50\n".encode("cp1252"));assert p["delimiter"]==";" and p["total"]==1
def test_decimal_comma_and_thousands(): assert parse_decimal("1.234,56 €")==1234.56
def test_spanish_and_iso_dates(): assert str(parse_date("01/02/2026"))=="2026-02-01" and str(parse_date("2026-02-01"))=="2026-02-01"
def test_invalid_rows_reported():
    good,bad=validate_rows([{"id":"1"},{"id":""}],{"external_id":"id"},{"external_id"});assert len(good)==1 and bad[0]["row"]==3
def test_excel_roundtrip(tmp_path):
    import pandas as pd
    p=tmp_path/"x.xlsx";pd.DataFrame([{"external_id":"A","amount":"2,5"}]).to_excel(p,index=False);assert ExcelConnector().preview(p)["total"]==1
