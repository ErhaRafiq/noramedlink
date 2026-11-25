"""Demo doctors for trying the home-visit service on a development database (scripts/home_visit_demo.py).

They are clearly labelled test accounts: every name starts with "[DEMO]", every email is
demo-homevisit-<key>@example.test, and the PMDC number starts with DEMO-. The coordinates are approximate
places in Islamabad, picked by hand; they are not real clinics. Nothing here is used by the app itself.
"""

from __future__ import annotations

from dataclasses import dataclass

NAME_PREFIX = "[DEMO] "
EMAIL_PREFIX = "demo-homevisit-"
EMAIL_SUFFIX = "@example.test"
HOSPITAL = "DEMO clinic (test account, not a real clinic)"


@dataclass(frozen=True)
class DemoDoctor:
    key: str
    name: str
    specialty: str
    area: str
    latitude: float
    longitude: float
    radius_km: float

    @property
    def email(self) -> str:
        return f"{EMAIL_PREFIX}{self.key}{EMAIL_SUFFIX}"

    @property
    def full_name(self) -> str:
        return f"{NAME_PREFIX}{self.name} ({self.area})"

    @property
    def pmdc(self) -> str:
        return f"DEMO-{self.key.upper()}"


DOCTORS = (
    DemoDoctor("f10", "Dr. Demo Farah", "General Physician", "F-10", 33.6938, 73.0129, 10),
    DemoDoctor("g11", "Dr. Demo Ghazal", "General Physician", "G-11", 33.6710, 72.9930, 10),
    DemoDoctor("bluearea", "Dr. Demo Bilal", "Dermatologist", "Blue Area", 33.7100, 73.0551, 10),
    DemoDoctor("bahria", "Dr. Demo Basit", "Pediatrician", "Bahria Town", 33.5240, 73.1190, 25),
)


def is_demo_account(email: str, full_name: str) -> bool:
    """Only an account matching both the email pattern and the name prefix is ever removed by the script."""
    return email.startswith(EMAIL_PREFIX) and email.endswith(EMAIL_SUFFIX) and full_name.startswith(NAME_PREFIX)
