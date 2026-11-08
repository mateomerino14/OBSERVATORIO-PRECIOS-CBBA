from datetime import date
from decimal import Decimal
from pathlib import Path

import psycopg
import pytest

from observatory.sources.paralelo import ParallelRateError, read_csv
from observatory.storage import save_exchange_rates

PROJECT_CSV = Path(__file__).parents[1] / "fuentes" / "dolar_paralelo" / "cierres_mensuales.csv"


def rates_by_month(rates) -> dict[str, Decimal]:
    return {f"{rate.day:%Y-%m}": rate.sell for rate in rates}


def test_project_csv_covers_august_2024_to_december_2025() -> None:
    months = rates_by_month(read_csv(PROJECT_CSV))

    assert min(months) == "2024-08"
    assert max(months) == "2025-12"
    assert len(months) == 17


def test_chained_closes_match_independent_anchors() -> None:
    months = rates_by_month(read_csv(PROJECT_CSV))

    # El boletín del 30-09-2025 trae un TOTAL de 81,03% sobre 6,97: Bs 12,62.
    assert months["2025-09"] == Decimal("12.62")
    # La prensa informó un cierre de 2025 de Bs 9,60.
    assert abs(months["2025-12"] - Decimal("9.60")) < Decimal("0.10")
    # El pico del paralelo fue en mayo de 2025.
    assert max(months, key=months.get) == "2025-05"


def test_rejects_unknown_method(tmp_path: Path) -> None:
    broken = tmp_path / "mal.csv"
    broken.write_text(
        "mes,fecha_dato,venta,metodo,fuente_url,nota\n2025-01,2025-01-31,11,adivinado,https://x,\n",
        encoding="utf-8",
    )

    with pytest.raises(ParallelRateError, match="adivinado"):
        read_csv(broken)


@pytest.mark.db
def test_import_stores_rates_as_parallel_source(db: psycopg.Connection) -> None:
    save_exchange_rates(db, "paralelo", read_csv(PROJECT_CSV))

    row = db.execute(
        "SELECT venta, compra FROM tipo_cambio WHERE fuente = 'paralelo' AND fecha = %s",
        (date(2025, 5, 31),),
    ).fetchone()
    assert row == (Decimal("16.39"), None)
