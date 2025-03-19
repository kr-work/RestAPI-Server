import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List

# import database
from uuid import UUID, uuid4

from fastapi import APIRouter, FastAPI, Path, WebSocket, WebSocketDisconnect
from psycopg_pool.abc import CT
from starlette.middleware.cors import CORSMiddleware
from uuid6 import uuid7

from src.crud import CollectID, CreateData, ReadData
from src.models.dc_models import (
    MatchModel,
    ScoreModel,
    ShotInfoModel,
    StateModel,
    StoneCoordinateModel,
)
from src.models.schema_models import (
    MatchDataSchema,
    PhysicalSimulatorSchema,
    PlayerSchema,
    ScoreSchema,
    ShotInfoSchema,
    StateSchema,
    StoneCoordinateSchema,
    TournamentSchema,
    TrajectorySchema,
)
from src.simulator import StoneSimulator

logging.basicConfig(level=logging.DEBUG)

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,   # 追記により追加
#     allow_methods=["*"],      # 追記により追加
#     allow_headers=["*"]       # 追記により追加
# )

try:
    sim = StoneSimulator()
except Exception as e:
    logging.error(f"Error in creating simulator: {e}")

rest_router = APIRouter()


class MatchAPI:
    @staticmethod
    @rest_router.get("/get_match/{match_id}", response_model=MatchDataSchema)
    async def get_match(match_id: UUID):
        match_data = await ReadData.read_match_data(match_id)
        return match_data

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
    @rest_router.get("/get_state/{state_id}", response_model=StateSchema)
    async def get_state(state_id: UUID):
        state_data = await ReadData.read_state_data(state_id)
        return state_data

    @staticmethod
    @rest_router.post("/add_state")
    async def add_state(state: StateModel):
        # logging.info(f"state: {state}")
        response = StateSchema(
            state_id=uuid7(),
            match_id=uuid7(),
            end_number=state.end_number,
            shot_number=state.shot_number,
            total_shot_number=state.total_shot_number,
            stone_coordinate_id=uuid7(),
            shot_id=uuid7(),
            created_at=datetime.now(),
        )
        logging.info(f"response: {response}")
        await CreateData.create_state_data(response)

    @staticmethod
    @rest_router.get("/collect_state", response_model=List[UUID])
    async def collect_state():
        state_id = await CollectID.collect_state_ids()
        return state_id


class StonePositionAPI:
    @staticmethod
    @rest_router.get(
        "/get_stone_coordinate/{stone_coordinate_id}",
        response_model=StoneCoordinateSchema,
    )
    async def get_stone_position(stone_coordinate_id: UUID):
        stone_data = await ReadData.read_stone_data(stone_coordinate_id)
        return stone_data

    @staticmethod
    @rest_router.post("/add_stone_coordinate")
    async def add_stone_position(stone: StoneCoordinateModel):
        stone_data_json = json.dumps(stone.stone_data)
        response = StoneCoordinateSchema(
            stone_coordinate_id=uuid7(),  # ここはstateを格納するときのidを使うため、後で変更する
            stone_coordinate_data=stone_data_json,
        )
        logging.info(f"response: {response}")
        await CreateData.create_stone_data(response)


class ScoreAPI:
    @staticmethod
    @rest_router.get("/get_score/{score_id}", response_model=ScoreSchema)
    async def get_score(score_id: UUID):
        logging.info(f"score_id: {score_id}")
        score_data = await ReadData.read_score_data(score_id)
        return score_data

    @staticmethod
    @rest_router.post("/add_score")
    async def add_score(score: ScoreModel):
        response = ScoreSchema(
            score_id=uuid7(),
            first_team_score=score.first_team_score,
            second_team_score=score.second_team_score,
        )
        logging.info(f"response: {response}")
        await CreateData.create_score_data(response)


class ShotInfoAPI:
    @staticmethod
    @rest_router.post("/add_shot_info")
    async def add_shot_info(shot: ShotInfoModel):
        response = ShotInfoSchema(
            shot_id=uuid7(),
            remaining_time=200.0,
            player_id=uuid7(),
            team_id=uuid7(),
            trajectory_id=uuid7(),
            pre_shot_state_id=uuid7(),
            post_shot_state_id=uuid7(),
            translation_velocity=shot.translation_velocity,
            rotation_velocity=shot.rotation_velocity,
            shot_angle=shot.shot_angle,
            simulate_flag=shot.simulate_flag,
        )
        logging.info(f"response: {response}")
        await CreateData.create_shot_info_data(response)