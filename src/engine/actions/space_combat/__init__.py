from __future__ import annotations

from typing import TYPE_CHECKING

from src.engine.core.game_state import CombatRoll

from . import afb_and_retreat, cleanup, opening, resolution

if TYPE_CHECKING:
    from src.engine.core.command import Command, CommandRule
    from src.engine.core.event import EventRule

AssignHitCommand = resolution.AssignHitCommand
RemoveCommandTokenFromPoolCommand = afb_and_retreat.RemoveCommandTokenFromPoolCommand
RemoveUnitCommand = cleanup.RemoveUnitCommand
RetreatShipCommand = afb_and_retreat.RetreatShipCommand
RollDiceForUnitEvent = resolution.RollDiceForUnitEvent

__all__ = [
    "AssignHitCommand",
    "CombatRoll",
    "RemoveCommandTokenFromPoolCommand",
    "RemoveUnitCommand",
    "RetreatShipCommand",
    "RollDiceForUnitEvent",
    "get_command_rules",
    "get_event_rules",
]


def get_command_rules() -> list[
    CommandRule[AssignHitCommand]
    | CommandRule[RetreatShipCommand]
    | CommandRule[RemoveCommandTokenFromPoolCommand]
    | CommandRule[RemoveUnitCommand]
    | CommandRule[Command]
]:
    return [
        resolution.AssignHitCommandRule(),
        afb_and_retreat.UseAntiFighterBarrageCommandRule(),
        afb_and_retreat.PassAntiFighterBarrageCommandRule(),
        opening.PassStartOfCombatWindowCommandRule(),
        afb_and_retreat.AnnounceRetreatCommandRule(),
        resolution.MakeCombatRollsCommandRule(),
        resolution.PassBeforeAssignHitsCommandRule(),
        afb_and_retreat.RetreatShipCommandRule(),
        afb_and_retreat.EndRetreatCommandRule(),
        afb_and_retreat.ChoosePoolToRemoveCommandTokenCommandRule(),
        opening.PassEndOfCombatWindowCommandRule(),
        cleanup.RemoveUnitDueToCapacityCommandRule(),
    ]


def get_event_rules() -> list[EventRule]:
    return [
        opening.OpenStartOfSpaceCombatWindowEventRule(),
        opening.SkipSpaceCombatIfOnlyOnePlayerHasShips(),
        resolution.EndSpaceCombatEventRule(),
        opening.CloseStartOfSpaceCombatRoundWindowsEventRule(),
        afb_and_retreat.CloseAntiFighterBarrageWindowEventRule(),
        afb_and_retreat.AdvanceToRollDiceStepEventRule(),
        resolution.AdvanceToAssignHitsStepEventRule(),
        resolution.DestroyUnitWhenAssignedHitEventRule(),
        resolution.AdvanceToRetreatStepEventRule(),
        resolution.OpenBeforeAssignHitsWindowEventRule(),
        resolution.SwitchAssigneeWhenFinishedAssigningEventRule(),
        afb_and_retreat.RemoveAbandonedFightersAndGroundForcesEventRule(),
        afb_and_retreat.PlaceCommandTokenInDestinationSystemIfAbleEventRule(),
        opening.CloseEndOfSpaceCombatRoundWindowsEventRule(),
        cleanup.CheckCapacityAfterCombatEventRule(),
        cleanup.RecheckCapacityAfterRemovalEventRule(),
        cleanup.ClearCombatStateAfterCombatEventRule(),
        resolution.CloseBeforeAssignHitsWindowIfAllHitsCancelledEventRule(),
    ]
