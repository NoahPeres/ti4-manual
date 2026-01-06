from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyCard:
    name: str
    initiative: int
    is_ready: bool = True

    @property
    def is_exhausted(self) -> bool:
        return not self.is_ready
