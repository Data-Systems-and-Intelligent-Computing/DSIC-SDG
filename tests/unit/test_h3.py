from __future__ import annotations

import unittest
from pathlib import Path

from kkciv_vintage.h3.geography import PROVINCE_KEYS, geo_level, normalise_name
from kkciv_vintage.h3.pipeline import (
    _discrepancies,
    classify,
    compare_sparse_sources,
    expand_publication_series,
    granularity_report,
)
from kkciv_vintage.h3.publication_tables import parse_page, read_column


ROOT = Path(__file__).resolve().parents[2]

# One appendix page reduced to three provinces, keeping the two features that
# break naive parsing: the diagonal watermark that splits a row across lines,
# and a footnote marker printed as a superscript glued onto the number.
PAGE = """ Lanjutan Lampiran 6
                                      Kode Indikator
       Provinsi              6.2.1* Akses terhadap sanitasi layak
                              2021          2022          2023
          (1)                  (2)           (3)           (4)
   Aceh                       77,55        77,48         78,85
   DKI Jakarta                95,17        92,79
                                                          93,501
   Papua Selatan                  –            –             …
   Indonesia                  80,29        80,92         82,36
 6.2.1*   Persentase rumah tangga
 Sumber:  Badan Pusat Statistik
"""


class GeographyTests(unittest.TestCase):
    def test_labels_from_both_channels_fold_to_one_key(self) -> None:
        self.assertEqual(normalise_name("<b>KEPULAUAN RIAU</b>"), normalise_name("Kep. Riau"))
        self.assertEqual(normalise_name("D I YOGYAKARTA"), normalise_name("DI Yogyakarta"))

    def test_thirty_eight_provinces_plus_the_national_aggregate(self) -> None:
        self.assertEqual(len(PROVINCE_KEYS), 39)
        self.assertEqual(len(set(PROVINCE_KEYS)), 39)

    def test_geo_level_follows_the_bps_code_shape(self) -> None:
        self.assertEqual(geo_level("9999"), "national")
        self.assertEqual(geo_level("1100"), "province")
        self.assertEqual(geo_level("1101"), "regency")


class PublicationTableTests(unittest.TestCase):
    def test_watermark_split_row_is_reassembled(self) -> None:
        parsed = parse_page(PAGE)
        self.assertEqual(parsed["columns"], ["2", "3", "4"])
        self.assertEqual(len(parsed["rows"]["DKIJAKARTA"]), 3)

    def test_superscript_footnote_is_split_from_the_value(self) -> None:
        column = read_column(parse_page(PAGE), "4")
        self.assertEqual(column["DKIJAKARTA"], {"value": "93.50", "note": "footnote_1"})
        self.assertEqual(column["ACEH"], {"value": "78.85", "note": ""})

    def test_withheld_and_not_yet_existing_cells_carry_no_value(self) -> None:
        column = read_column(parse_page(PAGE), "2")
        self.assertEqual(column["PAPUASELATAN"], {"value": "", "note": "not_published"})

    def test_committed_pages_yield_every_province(self) -> None:
        pdf = ROOT / "data/raw/h1/publications/bps_tpb_2024.pdf"
        if not pdf.exists():
            self.skipTest("publication PDF is not present; run `make h1-fetch-free-publications`")
        from kkciv_vintage.h3.publication_tables import extract_pages

        pages = extract_pages(pdf)
        for number in (254, 255, 269, 272, 274, 275, 276):
            parsed = parse_page(pages[number - 1])
            self.assertEqual(parsed["incomplete_rows"], {}, f"page {number}")
            self.assertEqual(len(parsed["rows"]), 39, f"page {number}")


class ClassificationTests(unittest.TestCase):
    def _cell(self, web: str, pub: str, spread: str, updated: str) -> dict[str, str]:
        return {
            "indicator_key": "x", "series_key": "total", "observed_period": "2023",
            "geo_level": "province", "geo_code": "1100", "geo_name": "Aceh", "unit": "percent",
            "absolute_spread": spread, "status": "value_mismatch",
            "observations_json": (
                '[{"source_id": "bps_webapi", "value": "%s", "methodology_version": "webapi-var-1-updated-%s"},'
                ' {"source_id": "bps_tpb_2024", "value": "%s", "methodology_version": "tpb-2024-appendix"}]'
                % (web, updated, pub)
            ),
        }

    def test_one_unit_in_the_last_place_is_not_called_a_revision(self) -> None:
        rows = classify([self._cell("88.11", "88.12", "0.01", "2026-07-07")], "2024-12-31")
        self.assertEqual(rows[0]["classification"], "last_digit_difference")

    def test_larger_gap_after_the_publication_date_is_a_candidate_revision(self) -> None:
        rows = classify([self._cell("12.04", "11.05", "0.99", "2026-07-07")], "2024-12-31")
        self.assertEqual(rows[0]["classification"], "candidate_revision")

    def test_exact_matches_are_not_reported(self) -> None:
        cell = self._cell("1", "1", "0", "2026-07-07")
        cell["status"] = "exact_match"
        self.assertEqual(classify([cell], "2024-12-31"), [])


class GranularityTests(unittest.TestCase):
    def test_national_is_compared_against_its_own_provinces(self) -> None:
        def row(level: str, code: str, value: str) -> dict[str, str]:
            return {
                "source_id": "bps_webapi", "indicator_key": "x", "series_key": "total",
                "observed_period": "2023", "unit": "percent",
                "geo_level": level, "geo_code": code, "value": value,
            }

        report = granularity_report(
            [row("national", "9999", "80"), row("province", "1100", "70"), row("province", "1200", "90")]
        )
        self.assertEqual(len(report), 1)
        self.assertEqual(report[0]["province_count"], "2")
        self.assertEqual(report[0]["province_unweighted_mean"], "80.0000")
        self.assertEqual(report[0]["national_within_province_range"], "yes")


class ReleaseSupplementTests(unittest.TestCase):
    def test_configured_publication_releases_expand_to_expected_cells(self) -> None:
        rows = expand_publication_series(ROOT / "config/h3/publication_series.csv")
        self.assertEqual(len(rows), 205)
        forest = [
            row
            for row in rows
            if row["source_id"] == "bps_tpb_2025"
            and row["indicator_key"] == "sdg15_forest_cover"
            and row["observed_period"] == "2022"
        ]
        self.assertEqual(forest[0]["value"], "51.16")

    def test_release_comparison_retains_sparse_and_conflicting_cells(self) -> None:
        def row(source: str, year: str, value: str) -> dict[str, str]:
            return {
                "source_id": source,
                "indicator_key": "sdg07_energy_intensity",
                "series_key": "total",
                "observed_period": year,
                "geo_level": "national",
                "geo_code": "9999",
                "geo_name": "Indonesia",
                "unit": "sbm_per_billion_rupiah",
                "value": value,
                "release_date": "2025-12-30",
                "producer": "ESDM",
                "methodology_version": "test",
                "source_record_id": f"{source}-{year}",
            }

        compared = compare_sparse_sources(
            [
                row("bps_webapi", "2018", "140.62"),
                row("bps_tpb_2024", "2018", "428.60"),
                row("bps_webapi", "2019", "141.00"),
            ],
            {"sdg07_energy_intensity": "energy"},
        )
        self.assertEqual([item["status"] for item in compared], ["value_mismatch", "single_source"])
        discrepancy = _discrepancies(compared)
        self.assertEqual(
            discrepancy[0]["candidate_classification"],
            "methodology_or_unit_change_candidate",
        )


if __name__ == "__main__":
    unittest.main()
