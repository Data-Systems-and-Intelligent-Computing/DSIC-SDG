from __future__ import annotations

import re


NATIONAL_CODE = "9999"
# The publication appendices and the WebAPI unit dimension list the same 38
# provinces in the same order, but spell a few of them differently.
NAME_ALIASES = {
    "DIYOGYAKARTA": "DIYOGYAKARTA",
    "DAERAHISTIMEWAYOGYAKARTA": "DIYOGYAKARTA",
    "KEPBANGKABELITUNG": "KEPBANGKABELITUNG",
    "KEPULAUANBANGKABELITUNG": "KEPBANGKABELITUNG",
    "KEPRIAU": "KEPULAUANRIAU",
    "DKIJAKARTA": "DKIJAKARTA",
}


def normalise_name(value: str) -> str:
    """Fold a province label to a comparison key.

    Strips the bold markup the WebAPI wraps around aggregates, then removes
    everything that the two channels punctuate differently.
    """
    value = re.sub(r"<[^>]+>", "", value)
    key = re.sub(r"[^A-Za-z]", "", value).upper()
    return NAME_ALIASES.get(key, key)


def geo_level(code: str) -> str:
    value = int(code)
    if value == 9999:
        return "national"
    return "province" if value % 100 == 0 else "regency"


# The 38 provinces plus the national aggregate, in the order both channels print
# them. Parsing an appendix page must recover every one of these.
PROVINCE_NAMES: tuple[str, ...] = (
    "Aceh", "Sumatera Utara", "Sumatera Barat", "Riau", "Jambi", "Sumatera Selatan",
    "Bengkulu", "Lampung", "Kep. Bangka Belitung", "Kepulauan Riau", "DKI Jakarta",
    "Jawa Barat", "Jawa Tengah", "DI Yogyakarta", "Jawa Timur", "Banten", "Bali",
    "Nusa Tenggara Barat", "Nusa Tenggara Timur", "Kalimantan Barat",
    "Kalimantan Tengah", "Kalimantan Selatan", "Kalimantan Timur", "Kalimantan Utara",
    "Sulawesi Utara", "Sulawesi Tengah", "Sulawesi Selatan", "Sulawesi Tenggara",
    "Gorontalo", "Sulawesi Barat", "Maluku", "Maluku Utara", "Papua Barat",
    "Papua Barat Daya", "Papua", "Papua Selatan", "Papua Tengah", "Papua Pegunungan",
    "Indonesia",
)
PROVINCE_KEYS: tuple[str, ...] = tuple(normalise_name(name) for name in PROVINCE_NAMES)
DISPLAY_NAMES: dict[str, str] = {
    normalise_name(name): name for name in PROVINCE_NAMES
}
