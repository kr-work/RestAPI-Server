"""DB service layer for match-related use cases.

- Routers should not touch DB sessions directly; they call this module.
- This layer owns session/transaction boundaries.
- Use CRUD helpers that do NOT commit inside session.begin().
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select

from src.crud import CreateData, ReadData, UpdateData
from src.db import Session
from src.domain.match_rules import generate_mixed_doubles_initial_stones
from src.models.dc_models import PositionedStonesModel
from src.models.schema_models import (
    MatchDataSchema,
    PlayerSchema,
    ShotInfoSchema,
    StateSchema,
    StoneCoordinateSchema,
)
from src.models.schemas import MatchMixDoublesSettings
from uuid6 import uuid7


async def read_match_data(match_id: UUID) -> MatchDataSchema | None:
    async with Session() as session:
        return await ReadData.read_match_data(match_id, session)


async def read_latest_state_data(match_id: UUID) -> StateSchema | None:
    async with Session() as session:
        return await ReadData.read_latest_state_data(match_id, session)


async def read_player_data(player_id: UUID) -> PlayerSchema | None:
    async with Session() as session:
        return await ReadData.read_player_data(player_id, session)


async def read_simulator_id(simulator_name: str) -> UUID | None:
    async with Session() as session:
        return await ReadData.read_simulator_id(simulator_name, session)


async def read_team_id(team_name: str) -> UUID | None:
    async with Session() as session:
        return await ReadData.read_team_id(team_name, session)


async def read_player_id(player_name: str, team_id: UUID) -> UUID | None:
    async with Session() as session:
        return await ReadData.read_player_id(player_name, team_id, session)


async def create_match_data(match_data: MatchDataSchema) -> None:
    async with Session() as session:
        success = await CreateData.create_match_data(match_data, session)
        if not success:
            raise RuntimeError("Failed to create match data")


async def create_state_data(state: StateSchema) -> None:
    async with Session() as session:
        success = await CreateData.create_state_data(state, session)
        if not success:
            raise RuntimeError("Failed to create state data")


async def create_player_data(player: PlayerSchema) -> None:
    async with Session() as session:
        success = await CreateData.create_player_data(player, session)
        if not success:
            raise RuntimeError("Failed to create player data")


async def record_shot_result(
    shot_info: ShotInfoSchema,
    post_state: StateSchema,
    pre_state_id: UUID,
) -> None:
    """Create shot_info + post state, then link pre_state.shot_id in one transaction.

    NOTE: Do not call CRUD helpers that commit() inside this transaction.
    """

    async with Session() as session:
        async with session.begin():
            await CreateData.add_shot_info_data(shot_info, session)
            await CreateData.add_state_data(post_state, session)
            await UpdateData.set_state_shot_id_no_commit(pre_state_id, shot_info.shot_id, session)


async def update_match_data_with_team_name(
    match_id: UUID,
    team_name: str,
    expected_match_team_name: str,
) -> str | None:
    async with Session() as session:
        return await UpdateData.update_match_data_with_team_name(
            match_id, session, team_name, expected_match_team_name
        )


async def update_first_team(match_id: UUID, team_id: UUID, player_id_list: list[UUID], team_name: str) -> None:
    async with Session() as session:
        await UpdateData.update_first_team(match_id, session, team_id, player_id_list, team_name)


async def update_second_team(match_id: UUID, team_id: UUID, player_id_list: list[UUID], team_name: str) -> None:
    async with Session() as session:
        await UpdateData.update_second_team(match_id, session, team_id, player_id_list, team_name)


async def update_next_shot_team(match_id: UUID, team_id: UUID) -> None:
    async with Session() as session:
        await UpdateData.update_next_shot_team(match_id, team_id, session)


async def update_score(score) -> None:
    async with Session() as session:
        await UpdateData.update_score(score, session)


async def perform_mix_doubles_end_setup(
    match_data: MatchDataSchema,
    latest_state: StateSchema,
    match_team_name: str,
    request: PositionedStonesModel,
) -> UUID:
    """DB-backed end-setup (transactional). Router should handle auth and redis publish."""

    async with Session() as session:
        async with session.begin():
            caller_team_id = (
                match_data.first_team_id if match_team_name == "team0" else match_data.second_team_id
            )
            other_team_id = (
                match_data.second_team_id if match_team_name == "team0" else match_data.first_team_id
            )
            caller_team_name = match_team_name
            other_team_name = "team1" if caller_team_name == "team0" else "team0"

            # Lock settings row to read/update power play usage and selector list.
            stmt = (
                select(MatchMixDoublesSettings)
                .where(MatchMixDoublesSettings.match_id == match_data.match_id)
                .with_for_update()
            )
            result = await session.execute(stmt)
            settings_row = result.scalars().first()
            if settings_row is None:
                raise RuntimeError("Mixed doubles settings row not found.")

            selector_list = settings_row.end_setup_team_ids or []
            # Seed list if missing (shouldn't happen in fresh DB).
            if not selector_list:
                selector_list = [str(match_data.second_team_id)]
                settings_row.end_setup_team_ids = selector_list

            if latest_state.end_number >= len(selector_list):
                raise RuntimeError("end_setup_team_ids is missing entries for current end.")

            expected_selector_team_id = UUID(str(selector_list[int(latest_state.end_number)]))
            if caller_team_id != expected_selector_team_id:
                raise ValueError("Not your turn to setup positioned stones.")

            # API input is a single enum. We derive power play side and whether to swap
            # which team gets the house/guard stone. The end_setup_team is treated as the
            # hammer team for the end (throws second).
            if request == PositionedStonesModel.pp_left:
                power_play_side = "left"
                hammer_stone_position = "guard"
            elif request == PositionedStonesModel.pp_right:
                power_play_side = "right"
                hammer_stone_position = "guard"
            elif request == PositionedStonesModel.center_house:
                power_play_side = None
                hammer_stone_position = "house"
            else:
                # PositionedStonesModel.center_guard
                power_play_side = None
                hammer_stone_position = "guard"

            power_play_requested = power_play_side in ("left", "right")

            first_throw_team_id = other_team_id
            hammer_team_name = caller_team_name

            if power_play_requested:
                used_end = (
                    settings_row.team0_power_play_end
                    if caller_team_name == "team0"
                    else settings_row.team1_power_play_end
                )
                if used_end is not None:
                    raise ValueError("Power play already used.")

                if caller_team_name == "team0":
                    settings_row.team0_power_play_end = int(latest_state.end_number)
                else:
                    settings_row.team1_power_play_end = int(latest_state.end_number)

            pattern = int(match_data.mix_doubles_settings.positioned_stones_pattern)
            stone_data = generate_mixed_doubles_initial_stones(
                hammer_team_name,
                power_play_side,
                pattern,
                hammer_stone_position=hammer_stone_position,
            )

            stone_coordinate = StoneCoordinateSchema(
                stone_coordinate_id=uuid7(),
                data=stone_data,
            )

            setup_state = StateSchema(
                state_id=uuid7(),
                winner_team_id=None,
                match_id=match_data.match_id,
                end_number=latest_state.end_number,
                shot_number=0,
                total_shot_number=0,
                first_team_remaining_time=latest_state.first_team_remaining_time,
                second_team_remaining_time=latest_state.second_team_remaining_time,
                first_team_extra_end_remaining_time=latest_state.first_team_extra_end_remaining_time,
                second_team_extra_end_remaining_time=latest_state.second_team_extra_end_remaining_time,
                stone_coordinate_id=stone_coordinate.stone_coordinate_id,
                score_id=latest_state.score_id,
                shot_id=None,
                next_shot_team_id=first_throw_team_id,
                created_at=datetime.now(),
                stone_coordinate=stone_coordinate,
            )
            await CreateData.add_state_data(setup_state, session)

            return setup_state.state_id


async def set_end_setup_team_for_end(
    *,
    match_id: UUID,
    end_number: int,
    selector_team_id: UUID,
) -> None:
    """Persist the selector (hammer) team for the given end_number.

    Stored as a JSONB list on match_mix_doubles_settings.end_setup_team_ids.
    """
    async with Session() as session:
        async with session.begin():
            stmt = (
                select(MatchMixDoublesSettings)
                .where(MatchMixDoublesSettings.match_id == match_id)
                .with_for_update()
            )
            result = await session.execute(stmt)
            settings_row = result.scalars().first()
            if settings_row is None:
                raise RuntimeError("Mixed doubles settings row not found.")

            selector_list = settings_row.end_setup_team_ids or []
            if not selector_list:
                # Seed end 0 if missing.
                selector_list = [str(selector_team_id)]

            if end_number < 0:
                raise ValueError("end_number must be >= 0")

            if end_number < len(selector_list):
                selector_list[end_number] = str(selector_team_id)
            elif end_number == len(selector_list):
                selector_list.append(str(selector_team_id))
            else:
                raise RuntimeError("end_setup_team_ids has a gap; cannot set future end without previous entries.")

            settings_row.end_setup_team_ids = selector_list
