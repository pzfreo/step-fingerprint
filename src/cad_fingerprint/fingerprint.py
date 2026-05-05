"""CadFingerprint — captures and stores a complete geometric fingerprint."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import analyze


@dataclass
class CadFingerprint:
    """Complete geometric fingerprint of a STEP or STL file.

    Intermediate representation between analysis and test generation.
    Can be serialized to JSON for inspection or loaded back for comparison.
    """

    file: str
    bounding_box: dict
    volume_and_area: dict
    moments_of_inertia: dict
    topology: dict
    face_inventory: list[dict]
    cross_sections: list[dict]
    radial_profile: list[dict]
    edge_inventory: list[dict] = field(default_factory=list)
    build_quality: dict = field(default_factory=dict)
    description: dict = field(default_factory=dict)
    source_format: str = "step"

    @classmethod
    def from_stl(
        cls,
        path: str | Path,
        axis: str = "Z",
        num_cross_sections: int = 20,
        num_radial_slices: int = 15,
        num_angles: int = 12,
    ) -> "CadFingerprint":
        """Analyze an STL file and return its fingerprint.

        Face inventory contains mesh-level stats only (no surface type
        classification — detect_primitives is not yet in a released build123d).
        Cross-sections and radial profile are fully functional.
        """
        data = analyze.analyze_stl(
            str(path),
            axis=axis,
            num_cross_sections=num_cross_sections,
            num_radial_slices=num_radial_slices,
            num_angles=num_angles,
        )
        return cls(**data)

    @classmethod
    def from_step(
        cls,
        path: str | Path,
        axis: str = "Z",
        num_cross_sections: int = 20,
        num_radial_slices: int = 15,
        num_angles: int = 12,
    ) -> "CadFingerprint":
        """Analyze a STEP file and return its fingerprint."""
        data = analyze.analyze_step(
            str(path),
            axis=axis,
            num_cross_sections=num_cross_sections,
            num_radial_slices=num_radial_slices,
            num_angles=num_angles,
        )
        return cls(**data)

    def to_json(self, path: Optional[str | Path] = None) -> str:
        """Serialize to JSON. Optionally write to file."""
        from dataclasses import asdict
        text = json.dumps(asdict(self), indent=2)
        if path:
            Path(path).write_text(text)
        return text

    @classmethod
    def from_json(cls, path: str | Path) -> "CadFingerprint":
        """Load a fingerprint from a JSON file."""
        data = json.loads(Path(path).read_text())
        return cls(**data)
