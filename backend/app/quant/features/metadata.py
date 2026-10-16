from dataclasses import dataclass
from typing import Dict, Any


@dataclass(frozen=True)
class FeatureDoc:
    name: str
    formula: str
    lookback: int
    warmup_period: int
    timestamp_alignment: str
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "formula": self.formula,
            "lookback": self.lookback,
            "warmup_period": self.warmup_period,
            "timestamp_alignment": self.timestamp_alignment,
            "description": self.description,
        }
