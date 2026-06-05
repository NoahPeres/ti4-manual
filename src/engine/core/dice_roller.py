import random
from typing import Protocol


class DiceRoller(Protocol):
    """Protocol for rolling dice.

    Implementations must return a list of exactly num_dice integer values."""

    def roll(self, num_dice: int) -> list[int]: ...


class NumberOfDiceMustBeNonNegativeError(ValueError):
    pass


class UniformDiceRoller(DiceRoller):
    def roll(self, num_dice: int) -> list[int]:
        if num_dice < 0:
            raise NumberOfDiceMustBeNonNegativeError
        return [random.randint(1, 10) for _ in range(num_dice)]
