import logging
from typing import List

from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import select

from src.crud import CollectID, ReadData
from src.db import Session
from src.routers.http_exceptions import not_found
from src.models.schemas import Match as MatchRow, ShotInfo as ShotInfoRow, State as StateRow
from src.models.schema_models import (
    MatchDataSchema,
    ScoreSchema,
    ShotInfoSchema,
    StateSchema,
    StoneCoordinateSchema,
)

logging.basicConfig(level=logging.DEBUG)

rest_router = APIRouter()


async def _resolve_latest_match_id_by_name(session, match_name: str) -> UUID:
    stmt = (
        select(MatchRow.match_id)
        .where(MatchRow.match_name == match_name)
        .order_by(MatchRow.started_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    match_id = result.scalars().first()
    if match_id is None:
        raise not_found("Match not found.")
    return match_id


class MatchAPI:
    @staticmethod
    @rest_router.get("/matches/{match_id}", response_model=MatchDataSchema)
    async def get_match(match_id: UUID):
        async with Session() as session:
            match_data = await ReadData.read_match_data(match_id, session)
            if match_data is None:
                raise not_found("Match not found.")
            return match_data

    @staticmethod
    @rest_router.get("/matches/by-name/latest", response_model=MatchDataSchema)
    async def get_match_by_name_latest(match_name: str = Query(..., min_length=1)):
        async with Session() as session:
            match_id = await _resolve_latest_match_id_by_name(session, match_name)
            match_data = await ReadData.read_match_data(match_id, session)
            if match_data is None:
                raise not_found("Match not found.")
            return match_data

    @staticmethod
    @rest_router.get("/matches/{match_id}/score", response_model=ScoreSchema)
    async def get_match_score(match_id: UUID):
        async with Session() as session:
            match_data = await ReadData.read_match_data(match_id, session)
            if match_data is None or match_data.score is None:
                raise not_found("Match not found.")
            return match_data.score

    @staticmethod
    @rest_router.get("/matches/by-name/score", response_model=ScoreSchema)
    async def get_match_score_by_name(match_name: str = Query(..., min_length=1)):
        async with Session() as session:
            match_id = await _resolve_latest_match_id_by_name(session, match_name)
            match_data = await ReadData.read_match_data(match_id, session)
            if match_data is None or match_data.score is None:
                raise not_found("Match not found.")
            return match_data.score

    @staticmethod
    @rest_router.get(
        "/matches/{match_id}/stone-coordinate/latest",
        response_model=StoneCoordinateSchema,
    )
    async def get_latest_stone_coordinate(match_id: UUID):
        async with Session() as session:
            latest_state = await ReadData.read_latest_state_data(match_id, session)
            if latest_state is None or latest_state.stone_coordinate is None:
                raise not_found("Stone coordinate not found.")
            return latest_state.stone_coordinate

    @staticmethod
    @rest_router.get(
        "/matches/by-name/stone-coordinate/latest",
        response_model=StoneCoordinateSchema,
    )
    async def get_latest_stone_coordinate_by_name(match_name: str = Query(..., min_length=1)):
        async with Session() as session:
            match_id = await _resolve_latest_match_id_by_name(session, match_name)
            latest_state = await ReadData.read_latest_state_data(match_id, session)
            if latest_state is None or latest_state.stone_coordinate is None:
                raise not_found("Stone coordinate not found.")
            return latest_state.stone_coordinate

    @staticmethod
    @rest_router.get("/matches/{match_id}/ends", response_model=List[int])
    async def list_match_ends(match_id: UUID):
        async with Session() as session:
            latest_state = await ReadData.read_latest_state_data(match_id, session)
            if latest_state is None:
                raise not_found("Match not found.")
            # Current end_number is the latest state's end_number.
            return list(range(0, int(latest_state.end_number) + 1))

    @staticmethod
    @rest_router.get("/matches/by-name/ends", response_model=List[int])
    async def list_match_ends_by_name(match_name: str = Query(..., min_length=1)):
        async with Session() as session:
            match_id = await _resolve_latest_match_id_by_name(session, match_name)
            latest_state = await ReadData.read_latest_state_data(match_id, session)
            if latest_state is None:
                raise not_found("Match not found.")
            return list(range(0, int(latest_state.end_number) + 1))

    @staticmethod
    @rest_router.get("/matches/{match_id}/latest-state", response_model=StateSchema)
    async def get_latest_state(match_id: UUID):
        async with Session() as session:
            state_data = await ReadData.read_latest_state_data(match_id, session)
            if state_data is None:
                raise not_found("State not found.")
            return state_data

    @staticmethod
    @rest_router.get("/matches/by-name/latest-state", response_model=StateSchema)
    async def get_latest_state_by_name(match_name: str = Query(..., min_length=1)):
        async with Session() as session:
            match_id = await _resolve_latest_match_id_by_name(session, match_name)
            state_data = await ReadData.read_latest_state_data(match_id, session)
            if state_data is None:
                raise not_found("State not found.")
            return state_data

    @staticmethod
    @rest_router.get(
        "/matches/{match_id}/ends/{end_number}/states",
        response_model=List[StateSchema],
    )
    async def get_states_in_end(match_id: UUID, end_number: int):
        async with Session() as session:
            return await ReadData.read_state_data_in_end(match_id, end_number, session)

    @staticmethod
    @rest_router.get(
        "/matches/by-name/ends/{end_number}/states",
        response_model=List[StateSchema],
    )
    async def get_states_in_end_by_name(
        end_number: int,
        match_name: str = Query(..., min_length=1),
    ):
        async with Session() as session:
            match_id = await _resolve_latest_match_id_by_name(session, match_name)
            return await ReadData.read_state_data_in_end(match_id, end_number, session)

    # @staticmethod
    # @rest_router.post("/add_match", response_model=MatchDataSchema)
    # async def add_match(match: MatchModel):
    #     response = MatchDataSchema(
    #         match_id=match.match_id,
    #         first_team_id=uuid7(),
    #         second_team_id=uuid7(),
    #         score_id=uuid7(),
    #         time_limit=match.time_limit,
    #         extra_end_time_limit=match.extra_end_time_limit,
    #         standard_end_count=match.standard_end_count,
    #         physical_simulator_id=uuid4(),
    #         tournament_id=uuid7(),
    #         match_name=match.match_name,
    #         created_at=datetime.fromtimestamp(0),
    #         started_at=datetime.fromtimestamp(0)
    #     )
    #     logging.info(f"response: {response}")
    #     await CreateData.create_match_data(response)


class StateAPI:
    @staticmethod
    @rest_router.get("/states/{state_id}", response_model=StateSchema)
    async def get_state(state_id: UUID):
        async with Session() as session:
            state_data = await ReadData.read_state_data(state_id, session)
            if state_data is None:
                raise not_found("State not found.")
            return state_data

    @staticmethod
    @rest_router.get("/states", response_model=List[UUID])
    async def collect_state():
        async with Session() as session:
            state_id = await CollectID.collect_state_ids(session)
            return state_id


class MatchShotsAPI:
    @staticmethod
    @rest_router.get(
        "/matches/{match_id}/ends/{end_number}/shots",
        response_model=List[ShotInfoSchema],
    )
    async def list_shots_in_end(match_id: UUID, end_number: int):
        async with Session() as session:
            # Ensure match exists (friendlier 404 than empty list on typo).
            match_data = await ReadData.read_match_data(match_id, session)
            if match_data is None:
                raise not_found("Match not found.")

            stmt = (
                select(ShotInfoRow)
                .join(StateRow, ShotInfoRow.post_shot_state_id == StateRow.state_id)
                .where(StateRow.match_id == match_id, StateRow.end_number == end_number)
                .order_by(StateRow.shot_number)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [ShotInfoSchema.model_validate(r) for r in rows]

    @staticmethod
    @rest_router.get(
        "/matches/by-name/ends/{end_number}/shots",
        response_model=List[ShotInfoSchema],
    )
    async def list_shots_in_end_by_name(
        end_number: int,
        match_name: str = Query(..., min_length=1),
    ):
        async with Session() as session:
            match_id = await _resolve_latest_match_id_by_name(session, match_name)
            stmt = (
                select(ShotInfoRow)
                .join(StateRow, ShotInfoRow.post_shot_state_id == StateRow.state_id)
                .where(StateRow.match_id == match_id, StateRow.end_number == end_number)
                .order_by(StateRow.shot_number)
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [ShotInfoSchema.model_validate(r) for r in rows]

    @staticmethod
    @rest_router.get(
        "/matches/{match_id}/ends/{end_number}/shots/{shot_number}",
        response_model=ShotInfoSchema,
    )
    async def get_shot_in_end(match_id: UUID, end_number: int, shot_number: int):
        async with Session() as session:
            stmt = (
                select(ShotInfoRow)
                .join(StateRow, ShotInfoRow.post_shot_state_id == StateRow.state_id)
                .where(
                    StateRow.match_id == match_id,
                    StateRow.end_number == end_number,
                    StateRow.shot_number == shot_number,
                )
                .limit(1)
            )
            result = await session.execute(stmt)
            row = result.scalars().first()
            if row is None:
                raise not_found("Shot info not found.")
            return ShotInfoSchema.model_validate(row)

    @staticmethod
    @rest_router.get(
        "/matches/{match_id}/shots/latest",
        response_model=ShotInfoSchema,
    )
    async def get_latest_shot(match_id: UUID):
        async with Session() as session:
            latest_state = await ReadData.read_latest_state_data(match_id, session)
            if latest_state is None:
                raise not_found("Match not found.")
            shot_info = await ReadData.read_last_shot_info_by_post_state_id(latest_state.state_id, session)
            if shot_info is None:
                raise not_found("Shot info not found.")
            return shot_info


class StonePositionAPI:
    @staticmethod
    @rest_router.get(
        "/stone_coordinate/{stone_coordinate_id}",
        response_model=StoneCoordinateSchema,
    )
    async def get_stone_position(stone_coordinate_id: UUID):
        async with Session() as session:
            stone_data = await ReadData.read_stone_data(stone_coordinate_id, session)
            if stone_data is None:
                raise not_found("Stone coordinate not found.")
            return stone_data


class ScoreAPI:
    @staticmethod
    @rest_router.get("/scores/{score_id}", response_model=ScoreSchema)
    async def get_score(score_id: UUID):
        logging.info(f"score_id: {score_id}")
        async with Session() as session:
            score_data = await ReadData.read_score_data(score_id, session)
            if score_data is None:
                raise not_found("Score not found.")
            return score_data


class ShotInfoAPI:
    @staticmethod
    @rest_router.get("/shots/{shot_id}", response_model=ShotInfoSchema)
    async def get_shot_info(shot_id: UUID):
        async with Session() as session:
            shot_info = await ReadData.read_shot_info_data(shot_id, session)
            if shot_info is None:
                raise not_found("Shot info not found.")
            return shot_info

    @staticmethod
    @rest_router.get(
        "/shots/by-post-state/{post_state_id}",
        response_model=ShotInfoSchema,
    )
    async def get_shot_info_by_post_state(post_state_id: UUID):
        async with Session() as session:
            shot_info = await ReadData.read_last_shot_info_by_post_state_id(post_state_id, session)
            if shot_info is None:
                raise not_found("Shot info not found.")
            return shot_info
