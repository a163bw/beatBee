from dataclasses import dataclass
from typing import Protocol

from .gate import can_publish
from .models import SearchSummary
from .summary import ManifestExporter


@dataclass(frozen=True, slots=True)
class PublicationOutcome:
    confirmed: bool
    message: str


class Publisher(Protocol):
    @property
    def available(self) -> bool:
        ...

    def publish(self, summary: SearchSummary) -> PublicationOutcome:
        ...


class UnavailablePublisher:
    @property
    def available(self) -> bool:
        return False

    def publish(self, summary: SearchSummary) -> PublicationOutcome:
        if not can_publish(summary):
            return PublicationOutcome(
                confirmed=False,
                message="Publishing blocked: not every result is OK.",
            )
        manifest = ManifestExporter().export(summary)
        return PublicationOutcome(
            confirmed=False,
            message=(
                "Publishing unavailable: no verified publisher is configured. "
                f"Ordered Master manifest: {manifest.to_dict()}"
            ),
        )
