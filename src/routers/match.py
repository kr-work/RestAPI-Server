import json
import logging
from datetime import datetime, timedelta
from typing import List
from uuid import UUID, uuid4
from uuid6 import uuid7
import numpy as np
from fastapi import APIRouter, Depends, status, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBasic
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from redis.asyncio import Redis

from src.crud import CreateData, ReadData, UpdateData
from src.models.dc_models import (
    ClientDataModel,
    CoordinateDataModel,
    ScoreModel,
    ShotInfoModel,
    StateModel,
    StoneCoordinateModel,
    TeamModel,
    MatchNameModel,
)
from src.models.schema_models import (
    MatchDataSchema,
    PhysicalSimulatorSchema,
    PlayerSchema,
    ScoreSchema,
    ShotInfoSchema,
    StateSchema,
    StoneCoordinateSchema,
    TeamSchema,
    TournamentSchema,
    TrajectorySchema,
)
from src.models.basic_authentication_models import UserModel
from src.create_postgres_engine import engine
from src.converter import DataConverter
from src.redis_subscriber import RedisSubscriber
from src.score_utils import ScoreUtils
from src.authentication.basic_authentication import BasicAuthentication
from src.authentication.basic_authentication_crud import (
    CreateAuthentication,
    ReadAuthentication,
    DeleteAuthentication,
)
from src.simulator import StoneSimulator

redis = Redis(host="redis", port=6379, decode_responses=True, health_check_interval=30)

match_router = APIRouter()
logging.basicConfig(level=logging.INFO)
Session = async_sessionmaker(
    autocommit=False, class_=AsyncSession, autoflush=True, bind=engine
)
security = HTTPBasic()
rest_router = APIRouter()
read_data = ReadData()
create_data = CreateData()
update_data = UpdateData()
data_converter = DataConverter()
read_authentication = ReadAuthentication()
create_authentication = CreateAuthentication()
delete_authentication = DeleteAuthentication()
score_utils = ScoreUtils()
basic_auth = BasicAuthentication()
stone_simulator = StoneSimulator()


def simulate_fcv1(
    shot_info: ShotInfoModel,
    state_data: StateSchema,
    total_shot_number: int,
    shot_per_team: int,
    team_number: int,
) -> tuple[np.ndarray, bool, np.ndarray]:
    """Stone simulation with fcv1 model

    Args:
        shot_info (ShotInfoModel): Adjusted shot information
        state_data (StateSchema): The latest state data of the match
        total_shot_number (int): Total number of shots
        shot_per_team (int): Number of shots per team
        team_number (int): Team"0" or Team"1"

    Returns:
        tuple[np.ndarray, bool, np.ndarray]: Simulated stone coordinate, five_lock_rule flag, trajectory
    """
    angle_radian = np.deg2rad(shot_info.shot_angle)
    velocity_x = shot_info.translation_velocity * np.cos(angle_radian)
    velocity_y = shot_info.translation_velocity * np.sin(angle_radian)
    angular_velocity_sign = shot_info.angular_velocity_sign
    stone_position = np.array(
        [
            coordinate
            for team, stones in state_data.stone_coordinate.stone_coordinate_data.items()
            for stone in stones
            for coordinate in (stone["x"], stone["y"])
        ]
    )
    angular_velocity_sign = 1
    if shot_info.angular_velocity_sign == "cw":
        angular_velocity_sign = 1
    elif shot_info.angular_velocity_sign == "ccw":
        angular_velocity_sign = -1

    simulated_stones_coordinate, trajectory = stone_simulator.simulator(
        stone_position,
        total_shot_number,
        velocity_x,
        velocity_y,
        angular_velocity_sign,
        team_number,
        shot_per_team,
    )
    return simulated_stones_coordinate, trajectory

async def state_end_number_update(
    state_data: StateSchema, next_shot_team_id: UUID, winner_team_id: UUID
) -> StateSchema:
    """Update the state data when the end number is updated

    Args:
        state_data (StateSchema): _description_

    Returns:
        StateSchema: _description_
    """
    stone_coordinate: StoneCoordinateSchema = reset_stone_coordinate()
    total_shot_number = 0

    state = StateSchema(
        state_id=uuid7(),
        winner_team_id=winner_team_id,
        match_id=state_data.match_id,
        end_number=state_data.end_number + 1,
        shot_number=int(total_shot_number / 2),
        total_shot_number=total_shot_number,
        first_team_remaining_time=state_data.first_team_remaining_time,
        second_team_remaining_time=state_data.second_team_remaining_time,
        first_team_extra_end_remaining_time=state_data.first_team_extra_end_remaining_time,
        second_team_extra_end_remaining_time=state_data.second_team_extra_end_remaining_time,
        stone_coordinate_id=stone_coordinate.stone_coordinate_id,
        score_id=state_data.score_id,
        shot_id=uuid7(),
        next_shot_team_id=next_shot_team_id,
        created_at=datetime.now(),
        stone_coordinate=stone_coordinate,
    )
    async with Session() as session:
        await create_data.create_state_data(state, session)
    channel = f"match:{state_data.match_id}"
    await redis.publish(channel, str(state_data.match_id))

def reset_stone_coordinate() -> StoneCoordinateSchema:
    """Reset the stone coordinate data

    Args:
        stone_coordinate (StoneCoordinateSchema): Stone coordinates for the 15th shot

    Returns:
        StoneCoordinateSchema: Reset the stone coordinate data
    """
    stone_coordinates_data = {
        "team0": [
            {"x": 0.0, "y": 0.0},
            {"x": 0.0, "y": 0.0},
            {"x": 0.0, "y": 0.0},
            {"x": 0.0, "y": 0.0},
            {"x": 0.0, "y": 0.0},
            {"x": 0.0, "y": 0.0},
            {"x": 0.0, "y": 0.0},
            {"x": 0.0, "y": 0.0},
        ],
        "team1": [
            {"x": 0.0, "y": 0.0},
            {"x": 0.0, "y": 0.0},
            {"x": 0.0, "y": 0.0},
            {"x": 0.0, "y": 0.0},
            {"x": 0.0, "y": 0.0},
            {"x": 0.0, "y": 0.0},
            {"x": 0.0, "y": 0.0},
            {"x": 0.0, "y": 0.0},
        ],
    }
    stone_coordinate = StoneCoordinateSchema(
        stone_coordinate_id=uuid7(),
        stone_coordinate_data=json.dumps(stone_coordinates_data),
    )
    return stone_coordinate


class BaseServer:
    @staticmethod
    @match_router.get("/start-match", response_model=UUID)
    async def start_match(
        client_data: ClientDataModel,
        user_data: UserModel = Depends(basic_auth.check_user_data),
    ) -> UUID:
        """Send the match_id to the client and Set up the match data

        Args:
            client_data (ClientDataModel):
                    tournament: TournamentNameModel
                    simulator: PhysicalSimulatorNameModel
                    time_limit: int
                    extra_end_time_limit: int
                    standard_end_count: int
                    match_name: str
            valid (bool): Basic authentication result

        Returns:
            UUID: send the match_id to the client
        """
        create_data = CreateData()
        match_id = uuid7()
        score_id = uuid7()
        simulator_id = uuid4()
        tournament_id = uuid7()
        stone_coordinates_id = uuid7()

        team_score = [0] * client_data.standard_end_count

        stone_coordinates_data = {
            "team0": [
                {"x": 0.0, "y": 0.0},
                {"x": 0.0, "y": 0.0},
                {"x": 0.0, "y": 0.0},
                {"x": 0.0, "y": 0.0},
                {"x": 0.0, "y": 0.0},
                {"x": 0.0, "y": 0.0},
                {"x": 0.0, "y": 0.0},
                {"x": 0.0, "y": 0.0},
            ],
            "team1": [
                {"x": 0.0, "y": 0.0},
                {"x": 0.0, "y": 0.0},
                {"x": 0.0, "y": 0.0},
                {"x": 0.0, "y": 0.0},
                {"x": 0.0, "y": 0.0},
                {"x": 0.0, "y": 0.0},
                {"x": 0.0, "y": 0.0},
                {"x": 0.0, "y": 0.0},
            ],
        }

        stone_coordinate = StoneCoordinateSchema(
            stone_coordinate_id=stone_coordinates_id,
            stone_coordinate_data=json.dumps(stone_coordinates_data),
        )

        state = StateSchema(
            state_id=uuid7(),
            winner_team_id=None,
            match_id=match_id,
            end_number=0,
            shot_number=0,
            total_shot_number=0,
            first_team_remaining_time=client_data.time_limit,
            second_team_remaining_time=client_data.time_limit,
            first_team_extra_end_remaining_time=client_data.extra_end_time_limit,
            second_team_extra_end_remaining_time=client_data.extra_end_time_limit,
            stone_coordinate_id=stone_coordinates_id,
            score_id=score_id,
            shot_id=uuid7(),
            next_shot_team_id="5050f20f-cf97-4fb1-bbc1-f2c9052e0d17",
            created_at=datetime.now(),
            stone_coordinate=stone_coordinate,
        )
        # Create score data
        score = ScoreSchema(
            score_id=score_id, team0_score=team_score, team1_score=team_score
        )
        # Create simulator data
        simulator = PhysicalSimulatorSchema(
            physical_simulator_id=simulator_id,
            simulator_name=client_data.simulator.simulator_name,
        )
        # Create tournament data
        tournament = TournamentSchema(
            tournament_id=tournament_id,
            tournament_name=client_data.tournament.tournament_name,
        )
        # Create match data
        match_data = MatchDataSchema(
            match_id=match_id,
            first_team_name=None,
            second_team_name=None,
            first_team_id="5050f20f-cf97-4fb1-bbc1-f2c9052e0d17",
            first_team_player1_id="006951d4-37b2-48eb-85a2-af9463a1e7aa",  # Set the ID of the player to be used in AI matches as default
            first_team_player2_id="006951d4-37b2-48eb-85a2-af9463a1e7aa",
            first_team_player3_id="006951d4-37b2-48eb-85a2-af9463a1e7aa",
            first_team_player4_id="006951d4-37b2-48eb-85a2-af9463a1e7aa",
            second_team_id="60e1e056-3613-4846-afc9-514ea7b6adde",
            second_team_player1_id="0eb2f8a5-bc94-40f2-9e0c-6d1300f2e7b0",  # Set the ID of the player to be used in AI matches as default
            second_team_player2_id="0eb2f8a5-bc94-40f2-9e0c-6d1300f2e7b0",
            second_team_player3_id="0eb2f8a5-bc94-40f2-9e0c-6d1300f2e7b0",
            second_team_player4_id="0eb2f8a5-bc94-40f2-9e0c-6d1300f2e7b0",
            winner_team_id=None,
            score_id=score_id,
            time_limit=client_data.time_limit,
            extra_end_time_limit=client_data.extra_end_time_limit,
            standard_end_count=client_data.standard_end_count,
            physical_simulator_id=simulator_id,
            tournament_id=tournament_id,
            match_name=client_data.match_name,
            created_at=datetime.now(),
            started_at=datetime.now(),
            score=score,
            simulator=simulator,
            tournament=tournament,
        )

        async with Session() as session:
            await create_data.create_match_data(match_data, session)
            await create_data.create_state_data(state, session)

        return match_id


class DCServer:
    @staticmethod
    @match_router.post("/store-team-config")
    async def store_team_config(
        match_id: UUID,
        expected_match_team_name: MatchNameModel,
        team_config_data: TeamModel,
        user_data: UserModel = Depends(basic_auth.check_user_data),
    ):
        """Store the team configuration data in the database

        Args:
            match_id (UUID): To identify the match
            expected_match_team_name (MatchNameModel):  The team name used in this match.
                                                        If you choose team0 to select the first attacker and your opponent has not yet set up team0, you can continue to use team0, and if your opponent uses team0, you become team1.
            team_config_data (TeamModel): The team configuration data
            user_data (UserModel): The user data for authentication
        """
        async with Session() as session:
            match_team_name = await update_data.update_match_data_with_team_name(
                match_id, session, team_config_data.team_name, expected_match_team_name
            )

            await basic_auth.create_match_data(
                user_data,
                match_id,
                match_team_name,
            )

            if match_team_name is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This match has already started.",
                )

            if team_config_data.use_default_config:
                logging.info("Using default config")
                return match_team_name

            team_id: UUID | None = await read_data.read_team_id(
                team_config_data.team_name, session
            )

            player_id_list: List[UUID] = []
            for i in range(1, 5):
                # 各チームごとに、player1, player2, player3, player4のIDを取得または生成
                player_name = getattr(team_config_data, f"player{i}").player_name
                player_id: UUID | None = await read_data.read_player_id(
                    player_name, team_id, session
                )
                if player_id is None:
                    player_id = uuid4()
                    player_data = PlayerSchema(
                        player_id=player_id,
                        team_id=team_id,
                        max_velocity=getattr(team_config_data, f"player{i}").max_velocity,
                        shot_dispersion_rate=getattr(
                            team_config_data, f"player{i}"
                        ).shot_dispersion_rate,
                        player_name=player_name,
                    )
                    await create_data.create_player_data(player_data, session)
                    player_id_list.append(player_id)
                else:
                    player_id_list.append(player_id)

            if match_team_name == "team0":
                await update_data.update_first_team(
                    match_id, session, player_id_list, team_config_data.team_name
                )
                await update_data.update_next_shot_team(match_id, session, team_id)
            elif match_team_name == "team1":
                await update_data.update_second_team(
                    match_id, session, player_id_list, team_config_data.team_name
                )

        return match_team_name

    @staticmethod
    @match_router.get("/stream/{match_id}")
    async def stream_state_info(
        match_id: UUID, user_data: UserModel = Depends(basic_auth.check_user_data)
    ):
        channel = f"match:{match_id}"
        redis_subscriber = RedisSubscriber(Session, match_id)

        return StreamingResponse(
            redis_subscriber.event_generator(channel, redis),
            media_type="text/event-stream; charset=utf-8",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    @staticmethod
    @match_router.post("/shot-info")
    async def receive_shot_info(
        match_id: UUID,
        shot_info: ShotInfoModel,
        user_data: UserModel = Depends(basic_auth.check_user_data),
    ) -> None:
        """Receive the shot information from the client

        Args:
            match_id (UUID): match_id
            shot_info (ShotInfoModel): shot information from the client

        """
        end_time: datetime = datetime.now()

        async with Session() as session:
            # Get match data to know simulator and team_id
            match_data: MatchDataSchema = await read_data.read_match_data(match_id, session)
            # Get latest state data to know total shot number, stone coordinate and remaining time and so on.
            pre_state_data: StateSchema = await read_data.read_latest_state_data(
                match_id, session
            )
            # Get match team name to know which team is sending the shot information
            match_team_name: str = await basic_auth.check_match_data(
                user_data, match_id
            )

            shot_team_name: str = (
                "team0"
                if pre_state_data.next_shot_team_id == match_data.first_team_id
                else "team1"
            )

            # Check if shot info which client sent is valid or not
            if shot_team_name != match_team_name:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Not your turn.",
                )

            winner_team_id: UUID = None
            next_shot_team_id: UUID = None
            player_id: UUID = None
            # shot team which send this "shot_info"
            shot_team_id: UUID = pre_state_data.next_shot_team_id
            # total shot number at this time
            total_shot_number: int = pre_state_data.total_shot_number
            shot_per_team: int = total_shot_number // 2
            player_number: int = int(total_shot_number / 4) + 1
            team_number: int = 0 if match_team_name == "team0" else 1

            if match_team_name == "team0":
                player_id = getattr(match_data, f"first_team_player{player_number}_id")
            elif match_team_name == "team1":
                player_id = getattr(match_data, f"second_team_player{player_number}_id")

            player_data = await read_data.read_player_data(player_id, session)
            dist_translation_velocity = np.max(
                [
                    np.min([shot_info.translation_velocity, player_data.max_velocity])
                    + np.random.normal(loc=0.0, scale=player_data.shot_dispersion_rate),
                    0.0,
                ]
            )

            dist_shot_info: ShotInfoModel = shot_info
            dist_shot_info.translation_velocity = dist_translation_velocity

            # Calculate the time difference between the last state and this shot
            # and update the remaining time
            pre_end_time: datetime = pre_state_data.created_at
            time_diff: timedelta = end_time - pre_end_time
            time_diff_seconds: float = time_diff.total_seconds()
            logging.info(f"time_diff_seconds: {time_diff_seconds}")

            team0_remaining_time: float = pre_state_data.first_team_remaining_time
            team1_remaining_time: float = pre_state_data.second_team_remaining_time
            team0_extra_end_remaining_time: float = pre_state_data.first_team_extra_end_remaining_time
            team1_extra_end_remaining_time: float = pre_state_data.second_team_extra_end_remaining_time

            if pre_state_data.end_number < match_data.standard_end_count:
                if match_team_name == "team0":
                    team0_remaining_time -= time_diff_seconds
                    if team0_remaining_time < 0:
                        winner_team_id = match_data.second_team_id
                        team0_remaining_time = 0
                elif match_team_name == "team1":
                    team1_remaining_time -= time_diff_seconds
                    if team1_remaining_time < 0:
                        winner_team_id = match_data.first_team_id
                        team1_remaining_time = 0
            else:
                if match_team_name == "team0":
                    team0_extra_end_remaining_time -= time_diff_seconds
                    if team0_extra_end_remaining_time < 0:
                        winner_team_id = match_data.second_team_id
                        team0_extra_end_remaining_time = 0
                elif match_team_name == "team1":
                    team1_extra_end_remaining_time -= time_diff_seconds
                    if team1_extra_end_remaining_time < 0:
                        winner_team_id = match_data.first_team_id
                        team1_extra_end_remaining_time = 0

            # Simulate the stone
            simulated_stones_coordinate, trajectory = simulate_fcv1(
                dist_shot_info, pre_state_data, total_shot_number, shot_per_team, team_number
            )

            # Update the total shot number and shot per team
            total_shot_number += 1
            shot_per_team = total_shot_number // 2

            # Check if the end is over
            if total_shot_number < 15:
                logging.info(f"total_shot_number(may be < 15): {total_shot_number}")
                next_shot_team_id = match_data.first_team_id if shot_team_id == match_data.second_team_id else match_data.second_team_id
            else:
                logging.info(f"total_shot_number: {total_shot_number}")
                next_shot_team_id = None

            shot_info_data = ShotInfoSchema(
                shot_id=uuid7(),
                player_id=player_id,
                team_id=shot_team_id,
                trajectory_id=uuid7(),
                pre_shot_state_id=pre_state_data.state_id,
                post_shot_state_id=uuid7(),
                actual_translation_velocity=shot_info.translation_velocity,
                translation_velocity=dist_translation_velocity,
                angular_velocity_sign=shot_info.angular_velocity_sign,
                angular_velocity=shot_info.angular_velocity,
                shot_angle=shot_info.shot_angle,
            )

            stone_coordinate = {
                "team0": [
                    {
                        "x": simulated_stones_coordinate[0][i][0],
                        "y": simulated_stones_coordinate[0][i][1],
                    }
                    for i in range(8)
                ],
                "team1": [
                    {
                        "x": simulated_stones_coordinate[1][i][0],
                        "y": simulated_stones_coordinate[1][i][1],
                    }
                    for i in range(8)
                ],
            }
            stone_coordinate_data = StoneCoordinateSchema(
                stone_coordinate_id=uuid7(),
                stone_coordinate_data=json.dumps(stone_coordinate),
            )
            # logging.info(f"stone_coordinate_data: {stone_coordinate_data}")

            state_data = StateSchema(
                state_id=shot_info_data.post_shot_state_id,
                winner_team_id=winner_team_id,
                match_id=match_id,
                end_number=pre_state_data.end_number,
                shot_number=shot_per_team,
                total_shot_number=total_shot_number,
                first_team_remaining_time=team0_remaining_time,
                second_team_remaining_time=team1_remaining_time,
                first_team_extra_end_remaining_time=team0_extra_end_remaining_time,
                second_team_extra_end_remaining_time=team1_extra_end_remaining_time,
                stone_coordinate_id=stone_coordinate_data.stone_coordinate_id,
                score_id=pre_state_data.score_id,
                shot_id=shot_info_data.shot_id,
                next_shot_team_id=next_shot_team_id,
                created_at=datetime.now(),
                stone_coordinate=stone_coordinate_data
            )
            await create_data.create_shot_info_data(shot_info_data, session)
            await create_data.create_state_data(state_data, session)

            channel = f"match:{match_id}"
            await redis.publish(channel, str(match_id))

            if total_shot_number == 15:
                # Update the score data
                pre_score_data: ScoreSchema = pre_state_data.score
                team0_score = pre_score_data.team0_score
                team1_score = pre_score_data.team1_score

                logging.info(f"simulated_stones_coordinate: {simulated_stones_coordinate}")

                team0_stones_position = [
                    (stone[0], stone[1])
                    for stone in simulated_stones_coordinate[0]
                ]
                team1_stones_position = [
                    (stone[0], stone[1])
                    for stone in simulated_stones_coordinate[1]
                ]
                distance_list = []
                for i in range(8):
                    distance_list.append(
                        score_utils.get_distance(0, team0_stones_position[i][0], team0_stones_position[i][1])
                    )
                    distance_list.append(
                        score_utils.get_distance(1, team1_stones_position[i][0], team1_stones_position[i][1])
                    )
                scored_team, score = score_utils.get_score(distance_list)
                if scored_team is None:
                    next_shot_team_id = match_data.first_team_id if match_team_name == "team1" else match_data.second_team_id
                elif scored_team == 0:
                    team0_score[state_data.end_number] = score
                    team1_score[state_data.end_number] = 0
                    next_shot_team_id = match_data.second_team_id
                elif scored_team == 1:
                    team0_score[state_data.end_number] = 0
                    team1_score[state_data.end_number] = score
                    next_shot_team_id = match_data.first_team_id

                score_data = ScoreSchema(
                    score_id=pre_score_data.score_id,
                    team0_score=team0_score,
                    team1_score=team1_score,
                )

                if state_data.end_number >= match_data.standard_end_count - 1:
                    team0_total_score = score_utils.calculate_score(team0_score)
                    team1_total_score = score_utils.calculate_score(team1_score)
                    if team0_total_score > team1_total_score:
                        next_shot_team_id = None
                        winner_team_id = match_data.first_team_id
                    elif team0_total_score < team1_total_score:
                        next_shot_team_id = None
                        winner_team_id = match_data.second_team_id
                    else:
                        winner_team_id = None

                await update_data.update_score(score_data, session)
                await state_end_number_update(state_data, next_shot_team_id, winner_team_id)
            

