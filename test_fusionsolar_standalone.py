"""
test_fusionsolar_standalone.py
==============================
Script de test autonome pour l'API FusionSolar (Huawei).
Zéro dépendance sur Home Assistant ou le projet FusionSolarPlus.

Dépendance :
    pip install requests

Utilisation :
    1. Connectez-vous manuellement sur https://uni003eu5.fusionsolar.huawei.com
    2. Installez l'extension "Cookie-Editor" : https://cookie-editor.com
    3. Cliquez sur "Export" (format JSON par défaut) → copiez tout
    4. Collez entre les triple-guillemets de COOKIES_JSON ci-dessous
    5. python test_fusionsolar_standalone.py
"""

import json
import logging
import time

import requests

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
SUBDOMAIN         = "uni003eu5"
CHARGER_DN        = "NE=237114670"
SMART_ASSISTANT_DN = "NE=237114668"

WORKING_MODE_OPTIONS = {"0": "Normal charge", "1": "PV Power Preferred"}
PV_PRIORITY_OPTIONS  = {"0": "Battery first", "1": "Appliances first"}

# Charger — None = read only
NEW_MAX_POWER_KW = None   # ex: 11.0
NEW_WORKING_MODE = None   # ex: "0" or "1"

# SmartAssistant — None = read only
NEW_PV_PRIORITY  = "1"   # ex: "0" = Battery first, "1" = Appliances first

# Collez ici le JSON exporté par Cookie-Editor (bouton "Export")
COOKIES_JSON = """
[
    {
        "name": "dp-session",
        "value": "x-5i5hpibx3vs9ld7tqm0bvwrz3udgo9pe6m8a44thrsleen8945uq8ade3s6lqp85o9k57xumjtny7t2k6kmnqqgbcbdcaksb9iap081iap06eotfeos5g607fvnxby47",
        "domain": ".fusionsolar.huawei.com",
        "hostOnly": false,
        "path": "/",
        "secure": true,
        "httpOnly": true,
        "sameSite": null,
        "session": true,
        "firstPartyDomain": "",
        "partitionKey": null,
        "storeId": null
    },
    {
        "name": "_abck",
        "value": "4CEC31A365B64627699D02D07E999966~0~YAAQtvoSAhWpWdyZAQAAJZ7d7A4sVq+kc5deR2J6HyfRTak7pRH/x0lnB5lksE6XADBioMYKPBcJ7NmFDQaLw/mjROWR2xZb6JnQeJLnUe8Uxvi6gR44jtdcm6Ocn+BZVQRoIfEG+8LkFwt99htB2t0Uqv/3KeYU+YxOtchsERnnmbehYj8w1zs0PqjBjnZ3pKzvoJS/gVODekPiHFeE2xOq30cW3vC+iCLJBE6xtSCAx9hL/JgjUYI+R14LfJzsgCdrDu+P+qE3Stk1VsJ3eBFEM5TjVZZTAMS+W25CipPVkU9AneJSrSa/SIS+Y3m1iIKXJpp+51s+6FVfPfhN4SNVla+n9mbBQt0xsgo8E1zf4/OkpTUhkJP0eWTYcIrXgMg01UJKtL2HPGrMT8PehkRmfp/bE5KnGxCVqYGDMbRbqvvys7sBRe6c/mbBM1Y0+UEUdpvIEtnRC62WL5aErFS4UgHqO2kE8bv41ynlP3DGcpxcrzdfS7vztAlbTvHATEvHww/NQ3NriCcNVZ56HNY3AUK7fbymEFnJPH2BwKrXld/WYuxgBdXrWk4FxzAd9XZd8vAQ6uLEiUqJ4exznOxxXowq6C94q8u9LbYsw9yUENhGB1Ki91etP11HQYbTon2jlRnuR5wX8wzvFIzNKFoU~-1~-1~-1~AAQAAAAE%2f%2f%2f%2f%2f7A6lwMWYX3Bungvfmf5NKWZ6MdtwxEDsvCBghfF+6xFasgovzgTExa0lCETnqTGYmcV4HOTK+YgVzfxr8VHzLt7KQYAodPoPfOR~-1",
        "domain": ".huawei.com",
        "hostOnly": false,
        "path": "/",
        "secure": true,
        "httpOnly": false,
        "sameSite": null,
        "session": false,
        "firstPartyDomain": "",
        "partitionKey": null,
        "expirationDate": 1792151570.993,
        "storeId": null
    },
    {
        "name": "utag_main",
        "value": "v_id:0199ebad51f1001b651afb20c67a05050011000d00bd0$_sn:13$_se:5$_ss:0$_st:1769762981896$ses_id:1769761163217%3Bexp-session$_pn:5%3Bexp-session",
        "domain": ".huawei.com",
        "hostOnly": false,
        "path": "/",
        "secure": false,
        "httpOnly": false,
        "sameSite": null,
        "session": false,
        "firstPartyDomain": "",
        "partitionKey": null,
        "expirationDate": 1801297181,
        "storeId": null
    },
    {
        "name": "_ga",
        "value": "GA1.1.1389914865.1765525815",
        "domain": ".huawei.com",
        "hostOnly": false,
        "path": "/",
        "secure": false,
        "httpOnly": false,
        "sameSite": null,
        "session": false,
        "firstPartyDomain": "",
        "partitionKey": null,
        "expirationDate": 1804321173.513,
        "storeId": null
    },
    {
        "name": "__hau",
        "value": "SUPPORTE.1772176255.1550487141",
        "domain": ".huawei.com",
        "hostOnly": false,
        "path": "/",
        "secure": false,
        "httpOnly": false,
        "sameSite": null,
        "session": false,
        "firstPartyDomain": "",
        "partitionKey": null,
        "expirationDate": 1803712255,
        "storeId": null
    },
    {
        "name": "HWWAFSESTIME",
        "value": "1773995610296",
        "domain": "uni003eu5.fusionsolar.huawei.com",
        "hostOnly": true,
        "path": "/",
        "secure": false,
        "httpOnly": false,
        "sameSite": null,
        "session": true,
        "firstPartyDomain": "",
        "partitionKey": null,
        "storeId": null
    },
    {
        "name": "support_last_vist",
        "value": "enterprise",
        "domain": ".huawei.com",
        "hostOnly": false,
        "path": "/",
        "secure": false,
        "httpOnly": false,
        "sameSite": null,
        "session": false,
        "firstPartyDomain": "",
        "partitionKey": null,
        "expirationDate": 1776522191.7,
        "storeId": null
    },
    {
        "name": "x-gray-tag",
        "value": "common",
        "domain": ".fusionsolar.huawei.com",
        "hostOnly": false,
        "path": "/",
        "secure": false,
        "httpOnly": false,
        "sameSite": null,
        "session": true,
        "firstPartyDomain": "",
        "partitionKey": null,
        "storeId": null
    },
    {
        "name": "SSO_TGC_",
        "value": "TGTX--F710527063-5622202-pbOr9hNU6lRXCs3OuxqKOfw2O6x6gtaDcIQ",
        "domain": ".fusionsolar.huawei.com",
        "hostOnly": false,
        "path": "/",
        "secure": true,
        "httpOnly": false,
        "sameSite": "lax",
        "session": true,
        "firstPartyDomain": "",
        "partitionKey": null,
        "storeId": null
    },
    {
        "name": "supportlang",
        "value": "en",
        "domain": ".huawei.com",
        "hostOnly": false,
        "path": "/",
        "secure": true,
        "httpOnly": false,
        "sameSite": null,
        "session": false,
        "firstPartyDomain": "",
        "partitionKey": null,
        "expirationDate": 1774768251.87,
        "storeId": null
    },
    {
        "name": "supportelang",
        "value": "en",
        "domain": ".huawei.com",
        "hostOnly": false,
        "path": "/",
        "secure": true,
        "httpOnly": false,
        "sameSite": null,
        "session": false,
        "firstPartyDomain": "",
        "partitionKey": null,
        "expirationDate": 1776522194.126,
        "storeId": null
    },
    {
        "name": "lang",
        "value": "en",
        "domain": ".huawei.com",
        "hostOnly": false,
        "path": "/",
        "secure": true,
        "httpOnly": false,
        "sameSite": null,
        "session": false,
        "firstPartyDomain": "",
        "partitionKey": null,
        "expirationDate": 1776522194.128,
        "storeId": null
    },
    {
        "name": "_ga_DYQ8BLWLFS",
        "value": "GS2.1.s1769761163$o5$g1$t1769761179$j44$l0$h0",
        "domain": ".huawei.com",
        "hostOnly": false,
        "path": "/",
        "secure": false,
        "httpOnly": false,
        "sameSite": null,
        "session": false,
        "firstPartyDomain": "",
        "partitionKey": null,
        "expirationDate": 1804321179.935,
        "storeId": null
    },
    {
        "name": "dp-session",
        "value": "x-obntmnqog79ckbqrdj6qbzaovt5i9fjt2l7x0avs5isbo5mrml5dfzbt2ortc87wdgg68b2rpjul8bbxenrs9cpctjelleionwrufx6rbweog6qptcjs48ph5c44lete",
        "domain": ".uni003eu5.fusionsolar.huawei.com",
        "hostOnly": false,
        "path": "/",
        "secure": true,
        "httpOnly": true,
        "sameSite": null,
        "session": false,
        "firstPartyDomain": "",
        "partitionKey": null,
        "expirationDate": 1773327093.954,
        "storeId": null
    },
    {
        "name": "enterpriselang",
        "value": "fr",
        "domain": ".huawei.com",
        "hostOnly": false,
        "path": "/",
        "secure": true,
        "httpOnly": false,
        "sameSite": null,
        "session": false,
        "firstPartyDomain": "",
        "partitionKey": null,
        "expirationDate": 1773646502.184,
        "storeId": null
    },
    {
        "name": "HWWAFSESID",
        "value": "1520a5e0de7d99cd36b",
        "domain": "uni003eu5.fusionsolar.huawei.com",
        "hostOnly": true,
        "path": "/",
        "secure": false,
        "httpOnly": false,
        "sameSite": null,
        "session": true,
        "firstPartyDomain": "",
        "partitionKey": null,
        "storeId": null
    },
    {
        "name": "idss_cid",
        "value": "13fc0d19-e6a2-40f8-b466-6ddc551bd126",
        "domain": ".huawei.com",
        "hostOnly": false,
        "path": "/",
        "secure": false,
        "httpOnly": false,
        "sameSite": null,
        "session": false,
        "firstPartyDomain": "",
        "partitionKey": null,
        "expirationDate": 1777901721,
        "storeId": null
    },
    {
        "name": "JSESSIONID",
        "value": "6AB1F9120108009526C58E2F6A87D21A",
        "domain": "uni003eu5.fusionsolar.huawei.com",
        "hostOnly": true,
        "path": "/",
        "secure": false,
        "httpOnly": true,
        "sameSite": null,
        "session": true,
        "firstPartyDomain": "",
        "partitionKey": null,
        "storeId": null
    },
    {
        "name": "locale",
        "value": "en-us",
        "domain": ".fusionsolar.huawei.com",
        "hostOnly": false,
        "path": "/",
        "secure": false,
        "httpOnly": false,
        "sameSite": null,
        "session": true,
        "firstPartyDomain": "",
        "partitionKey": null,
        "storeId": null
    },
    {
        "name": "pageversion",
        "value": "0",
        "domain": "uni003eu5.fusionsolar.huawei.com",
        "hostOnly": true,
        "path": "/",
        "secure": true,
        "httpOnly": false,
        "sameSite": "lax",
        "session": true,
        "firstPartyDomain": "",
        "partitionKey": null,
        "storeId": null
    },
    {
        "name": "selfSettingLanguage",
        "value": "true",
        "domain": ".fusionsolar.huawei.com",
        "hostOnly": false,
        "path": "/",
        "secure": true,
        "httpOnly": false,
        "sameSite": "lax",
        "session": true,
        "firstPartyDomain": "",
        "partitionKey": null,
        "storeId": null
    },
    {
        "name": "SSO_TGC_",
        "value": "TGTX--F710527063-4366128-ca4NHnc7E0kvprsa12ewN2VYGheGEDSsZXR",
        "domain": ".uni003eu5.fusionsolar.huawei.com",
        "hostOnly": false,
        "path": "/",
        "secure": true,
        "httpOnly": true,
        "sameSite": null,
        "session": false,
        "firstPartyDomain": "",
        "partitionKey": null,
        "expirationDate": 1773327093.954,
        "storeId": null
    },
    {
        "name": "x-gray-tag",
        "value": "common",
        "domain": ".uni003eu5.fusionsolar.huawei.com",
        "hostOnly": false,
        "path": "/",
        "secure": false,
        "httpOnly": false,
        "sameSite": null,
        "session": false,
        "firstPartyDomain": "",
        "partitionKey": null,
        "expirationDate": 1773327093.954,
        "storeId": null
    }
]
"""

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger("fsp_test")


def _section(title: str):
    print(f"\n{'═'*60}\n  {title}\n{'═'*60}")


# ─────────────────────────────────────────────────────────────────────────────
# Client
# ─────────────────────────────────────────────────────────────────────────────

class SimpleClient:
    """Client HTTP minimal basé sur des cookies de session navigateur."""

    def __init__(self, subdomain: str, cookies_json: str):
        self.subdomain  = subdomain
        self.base       = f"https://{subdomain}.fusionsolar.huawei.com"
        self.company_id = None

        self._session = requests.Session()
        self._session.headers["User-Agent"] = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/119.0.0.0 Safari/537.36"
        )
        self._load_cookies(cookies_json)

    def _load_cookies(self, cookies_json: str):
        """Injecte les cookies depuis le JSON exporté par Cookie-Editor.

        Format attendu : liste de dicts avec au moins "name", "value", "domain".
        """
        cookies = json.loads(cookies_json.strip())
        count = 0
        for c in cookies:
            name   = c.get("name", "").strip()
            value  = c.get("value", "").strip()
            domain = c.get("domain", f".{self.subdomain}.fusionsolar.huawei.com").lstrip(".")

            if not name or not value:
                continue

            # Ignorer les cookies avec des caractères non-latin1 (ex: _abck)
            try:
                value.encode("latin-1")
            except UnicodeEncodeError:
                log.debug("Cookie '%s' ignoré (valeur non-latin1)", name)
                continue

            self._session.cookies.set(name, value, domain=domain)
            count += 1
        log.info("✓ %d cookies chargés", count)

    def init(self):
        """Vérifie la session et récupère company_id + csrfToken frais."""
        _section("Vérification session")

        # keep-alive → vérifie que la session est active + récupère roarand
        r = self._session.get(f"{self.base}/rest/dpcloud/auth/v1/keep-alive")
        r.raise_for_status()
        ka = r.json()
        log.debug("keep-alive: %s", ka)
        if ka.get("code") != 0:
            raise RuntimeError(
                "Session invalide (code != 0).\n"
                "→ Re-connectez-vous dans le navigateur et re-exportez les cookies."
            )
        if ka.get("payload"):
            self._session.headers["roarand"] = ka["payload"]
            log.debug("roarand depuis keep-alive: %s", ka["payload"])

        # company_id
        r = self._session.get(
            f"{self.base}/rest/neteco/web/organization/v2/company/current",
            params={"_": round(time.time() * 1000)},
        )
        r.raise_for_status()
        resp_text = r.content.decode()
        if not resp_text.strip().startswith('{"data":'):
            raise RuntimeError(
                f"Réponse inattendue sur /company/current — session expirée ?\n"
                f"{resp_text[:300]}"
            )
        self.company_id = r.json()["data"]["moDn"]
        log.info("✓ Session active. company_id = %s", self.company_id)

    # ── Devices ───────────────────────────────────────────────────────────────

    def get_device_ids(self) -> list:
        r = self._session.get(
            f"{self.base}/rest/neteco/web/config/device/v1/device-list",
            params={
                "conditionParams.parentDn": self.company_id,
                "conditionParams.mocTypes": "20815,20816,20819,20822,50017,60066,60014,60015,23037,60080,20817,20851",
                "_": round(time.time() * 1000),
            },
        )
        r.raise_for_status()
        return [{"type": d["mocTypeName"], "deviceDn": d["dn"]} for d in r.json()["data"]]

    # ── Charger config ────────────────────────────────────────────────────────

    def _resolve_dn_id(self, device_dn: str) -> str:
        """Traduit un DN (ex: 'NE=237114670') en dnId numérique."""
        r = self._session.get(
            f"{self.base}/rest/pvms/web/device/v1/mo-details",
            params=(("dn", device_dn), ("_", round(time.time() * 1000))),
            allow_redirects=False,
        )
        if r.status_code in (301, 302, 303, 307, 308):
            raise RuntimeError(
                f"Session expirée lors de mo-details (redirect {r.status_code}).\n"
                "→ Re-connectez-vous et re-exportez les cookies."
            )
        r.raise_for_status()
        dn_id = str(r.json().get("data", {}).get("mo", {}).get("dnId", ""))
        log.debug("dnId pour %s = %s", device_dn, dn_id)
        return dn_id

    def _resolve_child_dn_id(self, device_dn: str) -> tuple:
        """Récupère le dnId ET le DN complet du charging pile enfant."""
        r = self._session.post(
            f"{self.base}/rest/dp/pvms/organization/v1/tree",
            json={
                "parentDn": device_dn,
                "treeDepth": "device",
                "pageParam": {"needPage": True},
                "filterCond": {"nameType": "device", "mocIdInclude": [60081]},
                "displayCond": {"self": False, "status": True},
            },
        )
        r.raise_for_status()
        tree = r.json()
        # Log complet pour voir tous les champs disponibles
        log.info("Arbre complet: %s", json.dumps(tree, indent=2))
        children = tree.get("childList", [])
        if not children:
            raise RuntimeError(f"Aucun device enfant (60081) trouvé pour {device_dn}")
        child = children[0]
        log.info("Child complet: %s", json.dumps(child, indent=2))
        child_dn_id = str(child["elementId"])
        child_dn = child.get("elementDn") or f"NE={child_dn_id}"
        log.info("Child dnId=%s  dn=%s", child_dn_id, child_dn)
        return child_dn_id, child_dn

    def get_charger_config(self, device_dn: str) -> dict:
        """Lit les paramètres de config du wallbox parent (get-config-info)."""
        dn_id = self._resolve_dn_id(device_dn)
        r = self._session.post(
            f"{self.base}/rest/neteco/web/homemgr/v1/device/get-config-info",
            json={"conditions": [{"dnId": dn_id, "queryAll": True}]},
            allow_redirects=False,
        )
        if r.status_code in (301, 302, 303, 307, 308):
            raise RuntimeError("Session expirée sur get-config-info.")
        r.raise_for_status()
        return r.json()

    def get_charger_pile_config(self, device_dn: str) -> dict:
        """Lit les paramètres de config du charging pile enfant."""
        child_dn_id, child_dn = self._resolve_child_dn_id(device_dn)
        r = self._session.post(
            f"{self.base}/rest/neteco/web/homemgr/v1/device/get-config-info",
            json={"conditions": [{"dnId": child_dn_id, "queryAll": True}]},
            allow_redirects=False,
        )
        r.raise_for_status()
        return r.json()

    def set_charger_max_charge_power(self, device_dn: str, max_power_kw: float) -> dict:
        """Modifie la limite supérieure de puissance de charge (signal id=20001)."""
        log.debug("set_charger_max_charge_power: dn=%s, valeur=%.2f kW", device_dn, max_power_kw)
        r = self._session.post(
            f"{self.base}/rest/neteco/config/device/v1/config/set-signal",
            data={
                "dn": device_dn,
                "changeValues": json.dumps([{"id": "20001", "value": str(max_power_kw)}]),
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            allow_redirects=False,
        )
        log.debug("set-signal HTTP %s : %s", r.status_code, r.text[:300])
        if r.status_code != 200:
            log.error("Échec set-signal HTTP %s : %s", r.status_code, r.text[:500])
        r.raise_for_status()
        return r.json()

    def _set_pile_signal(self, device_dn: str, signal_id: str, value: str) -> dict:
        """Envoie un set-signal sur le DN enfant (charging pile).
        Note: l'API retourne code=-1 même en cas de succès pour ce device.
        """
        child_dn_id, child_dn = self._resolve_child_dn_id(device_dn)

        # Formats à tester dans l'ordre
        dns_to_try = list(dict.fromkeys([
            child_dn,
            f"NE={child_dn_id}",
            device_dn,
        ]))

        for dn in dns_to_try:
            log.debug("set pile signal: dn=%s, id=%s, value=%s", dn, signal_id, value)
            r = self._session.post(
                f"{self.base}/rest/neteco/config/device/v1/config/set-signal",
                data={
                    "dn": dn,
                    "changeValues": json.dumps([{"id": signal_id, "value": value}]),
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                allow_redirects=False,
            )
            log.debug("set pile signal HTTP %s dn=%s : %s", r.status_code, dn, r.text[:300])
            if r.status_code == 200:
                # code=-1 semble être le comportement normal pour ce device (pas une erreur)
                log.info("✓ set-signal envoyé avec dn=%s (code=-1 = comportement normal)", dn)
                return r.json()
            else:
                log.warning("HTTP %s avec dn=%s : %s", r.status_code, dn, r.text[:200])

        r.raise_for_status()
        return r.json()

    def set_charger_working_mode(self, device_dn: str, mode) -> dict:
        """Modifie le mode de fonctionnement (signal id=20002).
        "0" = Normal charge, "1" = PV Power Preferred
        """
        mode = str(mode)
        if mode not in {"0", "1"}:
            raise ValueError(f"Mode invalide '{mode}'. Valeurs : 0=Normal charge, 1=PV Power Preferred")
        return self._set_pile_signal(device_dn, "20002", mode)

    def set_charger_load_priority(self, device_dn: str, value: int) -> dict:
        """Modifie la Load Priority (signal id=455782011).
        Valeurs probables à déterminer via l'app Android.
        """
        return self._set_pile_signal(device_dn, "455782011", str(value))

    def set_charger_battery_first(self, device_dn: str, enabled: bool) -> dict:
        """Enable/disable Dynamic Charge Power (signal id=538976529)."""
        value = "1" if enabled else "0"
        log.debug("set_charger_battery_first: dn=%s, enabled=%s → value=%s", device_dn, enabled, value)
        return self._set_pile_signal(device_dn, "538976529", value)

    # ── SmartAssistant ────────────────────────────────────────────────────────

    def get_smart_assistant_config(self, device_dn: str) -> dict:
        """Reads SmartAssistant config signals (get-config-info)."""
        r = self._session.get(
            f"{self.base}/rest/pvms/web/device/v1/mo-details",
            params=(("dn", device_dn), ("_", round(time.time() * 1000))),
            allow_redirects=False,
        )
        r.raise_for_status()
        dn_id = str(r.json().get("data", {}).get("mo", {}).get("dnId", ""))
        log.debug("SmartAssistant dnId for %s = %s", device_dn, dn_id)

        r = self._session.post(
            f"{self.base}/rest/neteco/web/homemgr/v1/device/get-config-info",
            json={"conditions": [{"dnId": dn_id, "queryAll": True}]},
            allow_redirects=False,
        )
        r.raise_for_status()
        return r.json()

    def set_smart_assistant_pv_priority(self, device_dn: str, priority: str) -> dict:
        """Sets PV Power Priority on SmartAssistant (signal id=230700180).
        "0" = Battery first, "1" = Appliances first
        """
        priority = str(priority)
        if priority not in {"0", "1"}:
            raise ValueError(f"Invalid priority '{priority}'. Valid: 0=Battery first, 1=Appliances first")
        log.debug("set_smart_assistant_pv_priority: dn=%s, priority=%s", device_dn, priority)
        r = self._session.post(
            f"{self.base}/rest/neteco/config/device/v1/config/set-signal",
            data={
                "dn": device_dn,
                "changeValues": json.dumps([{"id": "230700180", "value": priority}]),
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            allow_redirects=False,
        )
        log.debug("set_smart_assistant_pv_priority HTTP %s : %s", r.status_code, r.text[:300])
        if r.status_code != 200:
            log.error("Failed set_smart_assistant_pv_priority HTTP %s : %s", r.status_code, r.text[:500])
        r.raise_for_status()
        return r.json()


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    client = SimpleClient(SUBDOMAIN, COOKIES_JSON)
    client.init()

    # ── 1. List devices ───────────────────────────────────────────────────────
    _section("Available devices")
    devices = client.get_device_ids()
    for d in devices:
        markers = []
        if d["deviceDn"] == CHARGER_DN:
            markers.append("← charger")
        if d["deviceDn"] == SMART_ASSISTANT_DN:
            markers.append("← SmartAssistant")
        print(f"  {d['type']:35s}  {d['deviceDn']}  {' '.join(markers)}")

    # ── 2. Charger parent config ──────────────────────────────────────────────
    _section(f"get-config-info charger ({CHARGER_DN})")
    config = client.get_charger_config(CHARGER_DN)
    for dn_key, signals in config.items():
        if not isinstance(signals, list):
            continue
        for sig in signals:
            if sig.get("id") == 20001:
                print(f"  ► Charge Power Upper Limit (id=20001) : {sig['realValue']} {sig.get('unit','kW')}")
            if sig.get("id") == 20002:
                mode_label = WORKING_MODE_OPTIONS.get(sig.get("value", ""), sig.get("realValue", "?"))
                print(f"  ► Working Mode             (id=20002) : {mode_label} (value={sig.get('value')})")

    # ── 3. Charging pile child config ─────────────────────────────────────────
    _section(f"get-config-info charging pile child ({CHARGER_DN})")
    try:
        pile_config = client.get_charger_pile_config(CHARGER_DN)
        for dn_key, signals in pile_config.items():
            if not isinstance(signals, list):
                continue
            print(f"\n  Configurable signals (dnId={dn_key}) :")
            for sig in signals:
                if sig.get("name"):
                    enum_str = f"  {sig['enumMap']}" if sig.get("enumMap") else ""
                    print(f"    id={sig['id']:12}  {sig['name']:45}  value={sig.get('value')}{enum_str}")
    except Exception as e:
        log.error("Pile config failed: %s", e)

    # ── 4. SmartAssistant config ──────────────────────────────────────────────
    _section(f"get-config-info SmartAssistant ({SMART_ASSISTANT_DN})")
    try:
        sa_config = client.get_smart_assistant_config(SMART_ASSISTANT_DN)
        for dn_key, signals in sa_config.items():
            if not isinstance(signals, list):
                continue
            for sig in signals:
                if sig.get("id") == 230700180:
                    label = PV_PRIORITY_OPTIONS.get(sig.get("value", ""), sig.get("realValue", "?"))
                    print(f"  ► PV Power Priority (id=230700180) : {label} (value={sig.get('value')})")
                    print(f"    enumMap: {sig.get('enumMap')}")
    except Exception as e:
        log.error("SmartAssistant config failed: %s", e)

    # ── 5. Set max charge power ───────────────────────────────────────────────
    if NEW_MAX_POWER_KW is not None:
        _section(f"set-signal id=20001 → {NEW_MAX_POWER_KW} kW")
        result = client.set_charger_max_charge_power(CHARGER_DN, NEW_MAX_POWER_KW)
        print(f"  API response: {result}")
        config2 = client.get_charger_config(CHARGER_DN)
        for dn_key, signals in config2.items():
            if not isinstance(signals, list):
                continue
            for sig in signals:
                if sig.get("id") == 20001:
                    print(f"  ► Confirmed: {sig['realValue']} {sig.get('unit','kW')}")
    else:
        print("\n  (NEW_MAX_POWER_KW = None → skipped)")

    # ── 6. Set working mode ───────────────────────────────────────────────────
    if NEW_WORKING_MODE is not None:
        label = WORKING_MODE_OPTIONS.get(str(NEW_WORKING_MODE), "?")
        _section(f"set-signal id=20002 → {NEW_WORKING_MODE} ({label})")
        result = client.set_charger_working_mode(CHARGER_DN, NEW_WORKING_MODE)
        print(f"  API response: {result}")
        pile2 = client.get_charger_pile_config(CHARGER_DN)
        for dn_key, signals in pile2.items():
            if not isinstance(signals, list):
                continue
            for sig in signals:
                if sig.get("id") == 20002:
                    print(f"  ► Confirmed: {sig.get('realValue')} (value={sig.get('value')})")
    else:
        print("\n  (NEW_WORKING_MODE = None → skipped)")

    # ── 7. Set PV Power Priority (Battery First) ──────────────────────────────
    if NEW_PV_PRIORITY is not None:
        label = PV_PRIORITY_OPTIONS.get(str(NEW_PV_PRIORITY), "?")
        _section(f"set-signal id=230700180 → {NEW_PV_PRIORITY} ({label})")
        result = client.set_smart_assistant_pv_priority(SMART_ASSISTANT_DN, NEW_PV_PRIORITY)
        print(f"  API response: {result}")
        sa_config2 = client.get_smart_assistant_config(SMART_ASSISTANT_DN)
        for dn_key, signals in sa_config2.items():
            if not isinstance(signals, list):
                continue
            for sig in signals:
                if sig.get("id") == 230700180:
                    confirmed = PV_PRIORITY_OPTIONS.get(sig.get("value", ""), sig.get("realValue", "?"))
                    print(f"  ► Confirmed: {confirmed} (value={sig.get('value')})")
    else:
        print("\n  (NEW_PV_PRIORITY = None → skipped)")


if __name__ == "__main__":
    main()
