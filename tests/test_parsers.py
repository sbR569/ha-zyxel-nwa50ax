"""Regression tests for zyxel_ssh_api.py parsers, using real CLI captures.

See tests/fixtures/<firmware>/ for the raw captures this file exercises.
Every assertion here was verified against the actual fixture content before
being committed - these numbers are not guesses, they're what the real AP
returned (see fixture files for the exact source).
"""
from pathlib import Path

import pytest

from ha_zyxel.zyxel_ssh_api import ZyxelSSHAPI

FIXTURES = Path(__file__).parent / "fixtures"


def load(version: str, name: str) -> str:
    return (FIXTURES / version / name).read_text()


@pytest.fixture
def api():
    return ZyxelSSHAPI("10.0.20.2", "admin", "dummy-password")


# ---------------------------------------------------------------------------
# Firmware 7.12 - captures réelles (voir tests/fixtures/v712/)
# ---------------------------------------------------------------------------

def test_v712_version(api):
    info = api._parse_version(load("v712", "show_version.txt"))
    assert info["model"] == "NWA50AX"
    assert info["firmware"] == "V7.12(ABYW.0)"
    assert info["build_date"] == "2026-07-05 07:50:35"


def test_v712_uptime_without_days_prefix(api):
    # Moins de 24h d'uptime -> pas de préfixe "X days", juste HH:MM:SS.
    # Exerce spécifiquement le chemin de repli du parser.
    seconds = api._parse_uptime(load("v712", "show_system_uptime.txt"))
    assert seconds == 4 * 3600 + 39 * 60 + 44


def test_v712_cpu_four_cores(api):
    # Ce modèle/firmware a 4 coeurs, pas 2 comme le laissait supposer la doc
    # de référence - confirme que l'agrégation est bien générique.
    cpu = api._parse_cpu(load("v712", "show_cpu_all.txt"))
    assert len(cpu["cores"]) == 4
    assert cpu["current"] == (1 + 2 + 2 + 2) // 4
    assert cpu["avg_1min"] == (3 + 4 + 5 + 2) // 4
    assert cpu["avg_5min"] == (3 + 3 + 4 + 3) // 4


def test_v712_memory_no_space_before_percent(api):
    # "memory usage: 53%" (pas d'espace avant le %) - confirme la tolérance.
    assert api._parse_memory(load("v712", "show_mem_status.txt")) == 53


def test_v712_wlan_four_ssids_including_new_one(api):
    # 4 SSIDs configurés (Home/Guest/IoT/Studio) au lieu des 3 attendus par
    # la doc de référence - confirme l'extraction générique par slot.
    # Couvre aussi un bug latent trouvé en écrivant ce test : les profils
    # SSID vides en fin de liste (SSID_profile_5 à 8) polluaient la capture
    # du profil précédent avant la correction du regex (voir le commentaire
    # dans _parse_wlan).
    radio = api._parse_wlan(load("v712", "show_wlan_all.txt"))
    assert radio["slot1_active"] is True
    assert radio["slot2_active"] is True
    assert set(radio["slot1_ssids"]) == {"Home", "Guest", "IoT", "Studio"}
    assert set(radio["slot2_ssids"]) == {"Home", "Guest", "IoT"}
    assert radio["slot1_band"] == "2.4G"
    assert radio["slot2_band"] == "5G"


def test_v712_clients_band_format_has_hz_suffix(api):
    # Point de fragilité identifié : le firmware 7.12 renvoie "2.4GHz"/"5GHz"
    # (pas "2.4G"/"5G" comme documenté ailleurs dans le CLI). Ce test fige le
    # format réellement observé, pour être alerté si un futur firmware change
    # encore ce champ.
    clients = api._parse_clients(load("v712", "show_wireless_hal_station_info.txt"))
    assert len(clients) == 4
    bands = {c["band"] for c in clients}
    assert bands == {"2.4GHz", "5GHz"}

    first = clients[0]
    assert first["mac"] == "AA:BB:CC:00:00:01"
    assert first["ip"] == "10.0.20.208"
    assert first["ssid"] == "MyHome"


def test_v712_interfaces(api):
    network = api._parse_interfaces(load("v712", "show_interface_all.txt"))
    assert network["ip_address"] == "10.0.20.2"
    assert network["netmask"] == "255.255.255.0"
    names = {i["name"] for i in network["interfaces"]}
    assert "lan" in names
    assert "wlan-1-1" in names


def test_v712_port_status(api):
    port = api._parse_port_status(load("v712", "show_port_status.txt"))
    assert port["status"] == "1000M/Full"
    assert port["speed"] == "1000M"
    assert port["tx_rate"] == 11010
    assert port["rx_rate"] == 6586
    assert port["uptime"] == "04:38:31"
    assert port["tx_bytes"] == 287578429
    assert port["rx_bytes"] == 2055519298


@pytest.mark.parametrize("name,expected", [
    ("show_wlan_ssid_profile_home.txt", True),
    ("show_wlan_ssid_profile_guest.txt", True),
    ("show_wlan_ssid_profile_iot.txt", False),
    ("show_wlan_ssid_profile_studio.txt", False),
])
def test_v712_ssid_schedule_mode(api, name, expected):
    assert api._parse_ssid_schedule_mode(load("v712", name)) is expected


# ---------------------------------------------------------------------------
# NWA130BE firmware 7.40 - captures réelles, anonymisées (MAC/IP/SSID) et
# raccourcies à 6 clients (voir tests/fixtures/nwa130be_v740/). Tri-bande
# (slot1 2.4G / slot2 5G / slot3 6G), Wi-Fi 7 avec MLO, 2 ports Ethernet.
# ---------------------------------------------------------------------------

NWA130BE = "nwa130be_v740"


def test_nwa130be_version(api):
    info = api._parse_version(load(NWA130BE, "show_version.txt"))
    assert info["model"] == "NWA130BE"
    assert info["firmware"] == "V7.40(ACIL.1)"


def test_nwa130be_uptime_with_days(api):
    seconds = api._parse_uptime(load(NWA130BE, "show_system_uptime.txt"))
    assert seconds == 30 * 86400 + 22 * 3600 + 49 * 60 + 39


def test_nwa130be_cpu_and_memory(api):
    cpu = api._parse_cpu(load(NWA130BE, "show_cpu_all.txt"))
    assert cpu["cores"] == [6, 4, 4, 4]
    assert api._parse_memory(load(NWA130BE, "show_mem_status.txt")) == 45


def test_nwa130be_wlan_lists_all_three_slots(api):
    radio = api._parse_wlan(load(NWA130BE, "show_wlan_all.txt"))
    assert radio["slots"] == [1, 2, 3]
    assert radio["slot3_active"] is True
    assert radio["slot3_band"] == "6G"
    assert radio["slot3_ssids"] == ["Wiz_SSID_1", "Wiz_SSID_5", "Wiz_SSID_4"]


def test_nwa130be_wlan_slot2_does_not_swallow_slot3(api):
    # Avant : le bloc slot2 s'étendait jusqu'à la fin de la sortie, et
    # récupérait donc aussi les SSIDs de slot3 (en double).
    radio = api._parse_wlan(load(NWA130BE, "show_wlan_all.txt"))
    assert radio["slot2_band"] == "5G"
    assert radio["slot2_ssids"] == ["Wiz_SSID_1", "Wiz_SSID_5", "Wiz_SSID_4"]


def test_known_ssids_include_ssids_only_on_slot3(api):
    output = (
        "slot: slot1\n SSID_profile_1: Home\n Activate: yes\n Band: 2.4G\n"
        "slot: slot2\n SSID_profile_1: Home\n Activate: yes\n Band: 5G\n"
        "slot: slot3\n SSID_profile_1: SixOnly\n Activate: yes\n Band: 6G\n"
    )
    api._item_registry["radio"].apply({}, [output])
    assert api._known_ssids == ["Home", "SixOnly"]


def test_nwa130be_clients_bands_and_mlo(api):
    clients = api._parse_clients(load(NWA130BE, "show_wireless_hal_station_info.txt"))
    assert len(clients) == 6
    assert [c["band"] for c in clients] == ["2.4GHz", "6GHz", "5GHz", "5GHz", "2.4GHz", "6GHz"]
    assert [c["mlo"] for c in clients] == [False, True, False, False, False, False]
    assert clients[1]["slot"] == 3
    assert clients[1]["tx_rate"] == 1729


def test_clients_without_mlo_field_report_none(api):
    # Le firmware NWA50AX 7.12 n'a pas de champ "MLO:" : None, pas False.
    clients = api._parse_clients(load("v712", "show_wireless_hal_station_info.txt"))
    assert all(c["mlo"] is None for c in clients)


def test_nwa130be_port_status_first_port_unchanged(api):
    port = api._parse_port_status(load(NWA130BE, "show_port_status.txt"))
    assert port["status"] == "2500M/Full"
    assert port["speed"] == "2500M"
    assert port["tx_bytes"] == 23577084343
    assert port["rx_bytes"] == 1112230717821
    assert port["uptime"] == "742:47:19"


def test_nwa130be_port_status_lists_every_port(api):
    port = api._parse_port_status(load(NWA130BE, "show_port_status.txt"))
    assert [p["port"] for p in port["ports"]] == [1, 2]
    assert port["ports"][1]["status"] == "Down"
    assert port["ports"][1]["speed"] is None


def test_v712_port_status_lists_single_port(api):
    port = api._parse_port_status(load("v712", "show_port_status.txt"))
    assert [p["port"] for p in port["ports"]] == [1]


def test_v712_wlan_reports_two_slots(api):
    radio = api._parse_wlan(load("v712", "show_wlan_all.txt"))
    assert radio["slots"] == [1, 2]


# ---------------------------------------------------------------------------
# Sémantique None (revue de code #3) : un format non reconnu doit renvoyer
# None, jamais 0/False, pour ne jamais se confondre avec une vraie mesure.
# ---------------------------------------------------------------------------

def test_unrecognized_format_returns_none_not_zero(api):
    garbage = "n'importe quoi qui ne matche aucun format connu"

    assert api._parse_memory(garbage) is None
    assert api._parse_uptime(garbage) is None

    cpu = api._parse_cpu(garbage)
    assert cpu["current"] is None
    assert cpu["avg_1min"] is None
    assert cpu["avg_5min"] is None

    radio = api._parse_wlan(garbage)
    assert radio["slot1_active"] is None
    assert radio["slot2_active"] is None

    port = api._parse_port_status(garbage)
    assert port["tx_rate"] is None
    assert port["status"] is None


def test_unrecognized_format_yields_no_slots_and_no_ports(api):
    garbage = "n'importe quoi qui ne matche aucun format connu"
    assert api._parse_wlan(garbage)["slots"] == []
    assert api._parse_port_status(garbage)["ports"] == []


# ---------------------------------------------------------------------------
# Tolérance des regex (revue de code #4)
# ---------------------------------------------------------------------------

def test_regex_tolerant_to_case_and_spacing(api):
    # Le format réel observé n'a jamais changé entre 7.10 et 7.12, mais les
    # regex sont désormais tolérantes par précaution face à un futur firmware.
    assert api._parse_memory("Memory Usage:53 %") == 53
    assert api._parse_memory("MEMORY   USAGE : 53%") == 53
