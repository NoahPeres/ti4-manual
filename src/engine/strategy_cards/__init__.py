from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyCard:
    name: str
    initiative: int
