import random
from typing import Protocol


class DiceRoller(Protocol):
    def roll(self, num_dice: int) -> list[int]: ...


class UniformDiceRoller(DiceRoller):
    def roll(self, num_dice: int) -> list[int]:
        return [random.randint(1, 10) for _ in range(num_dice)]
