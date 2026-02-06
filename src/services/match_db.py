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
from src.models.dc_models import EndSetupRequestModel
from src.models.schema_models import (
    MatchDataSchema,
    PlayerSchema,
    ShotInfoSchema,
    StateSchema,
    StoneCoordinateSchema,
)
from src.models.schemas import MatchMixDoublesEndSetup, MatchMixDoublesSettings
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


async def read_mix_doubles_end_setup(match_id: UUID, end_number: int) -> MatchMixDoublesEndSetup | None:
    async with Session() as session:
        return await ReadData.read_mix_doubles_end_setup(match_id, end_number, session)


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


async def create_mix_doubles_end_setup(match_id: UUID, end_number: int, end_setup_team_id: UUID) -> None:
    async with Session() as session:
        success = await CreateData.create_mix_doubles_end_setup(
            match_id=match_id,
            end_number=end_number,
            end_setup_team_id=end_setup_team_id,
            session=session,
        )
        if not success:
            raise RuntimeError("Failed to create mix doubles end setup")


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


async def update_first_team(match_id: UUID, player_id_list: list[UUID], team_name: str) -> None:
    async with Session() as session:
        await UpdateData.update_first_team(match_id, session, player_id_list, team_name)


async def update_second_team(match_id: UUID, player_id_list: list[UUID], team_name: str) -> None:
    async with Session() as session:
        await UpdateData.update_second_team(match_id, session, player_id_list, team_name)


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
    request: EndSetupRequestModel,
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

            stmt = (
                select(MatchMixDoublesEndSetup)
                .where(
                    MatchMixDoublesEndSetup.match_id == match_data.match_id,
                    MatchMixDoublesEndSetup.end_number == latest_state.end_number,
                )
                .with_for_update()
            )
            result = await session.execute(stmt)
            end_setup_row = result.scalars().first()

            if end_setup_row is None:
                end_setup_row = MatchMixDoublesEndSetup(
                    match_id=match_data.match_id,
                    end_number=latest_state.end_number,
                    end_setup_team_id=match_data.first_team_id,
                    setup_done=False,
                )
                session.add(end_setup_row)
                await session.flush()

            if end_setup_row.setup_done:
                raise ValueError("End setup already completed.")

            if caller_team_id != end_setup_row.end_setup_team_id:
                raise ValueError("Not your turn to setup positioned stones.")

            power_play_side: str | None = request.power_play_side
            power_play_requested = power_play_side in ("left", "right")

            if request.selector_throws_first and power_play_requested:
                raise ValueError("power_play_side can only be used when selector_throws_first is false.")

            if request.selector_throws_first:
                first_throw_team_id = caller_team_id
                hammer_team_name = other_team_name
            else:
                first_throw_team_id = other_team_id
                hammer_team_name = caller_team_name

            if power_play_requested:
                used_end = (
                    match_data.mix_doubles_settings.team0_power_play_end
                    if caller_team_name == "team0"
                    else match_data.mix_doubles_settings.team1_power_play_end
                )
                if used_end is not None:
                    raise ValueError("Power play already used.")

                stmt = (
                    select(MatchMixDoublesSettings)
                    .where(MatchMixDoublesSettings.match_id == match_data.match_id)
                    .with_for_update()
                )
                result = await session.execute(stmt)
                settings_row = result.scalars().first()
                if settings_row is not None:
                    if caller_team_name == "team0":
                        settings_row.team0_power_play_end = int(latest_state.end_number)
                    else:
                        settings_row.team1_power_play_end = int(latest_state.end_number)

            pattern = int(match_data.mix_doubles_settings.positioned_stones_pattern)
            stone_data = generate_mixed_doubles_initial_stones(
                hammer_team_name,
                power_play_side,
                pattern,
            )

            stone_coordinate = StoneCoordinateSchema(
                stone_coordinate_id=uuid7(),
                data=stone_data,
            )

            end_setup_row.setup_done = True

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


async def upsert_next_end_setup_selector(
    match_id: UUID,
    next_end_number: int,
    next_selector_team_id: UUID,
) -> None:
    async with Session() as session:
        stmt = select(MatchMixDoublesEndSetup).where(
            MatchMixDoublesEndSetup.match_id == match_id,
            MatchMixDoublesEndSetup.end_number == next_end_number,
        )
        result = await session.execute(stmt)
        row = result.scalars().first()
        if row is None:
            row = MatchMixDoublesEndSetup(
                match_id=match_id,
                end_number=next_end_number,
                end_setup_team_id=next_selector_team_id,
                setup_done=False,
            )
            session.add(row)
        else:
            row.end_setup_team_id = next_selector_team_id
            row.setup_done = False
        await session.commit()
