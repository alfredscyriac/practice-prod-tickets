from dataclasses import dataclass, field
from typing import Dict

from nyc_health.models.bed import WardType
from nyc_health.models.patient import Borough


@dataclass
class Hospital:
    id: str
    name: str
    borough: Borough
    ward_targets: Dict[WardType, int] = field(default_factory=dict)  # planned bed counts per ward
