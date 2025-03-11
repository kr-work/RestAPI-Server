import asyncio
import json
import logging
from datetime import datetime
from typing import List
from uuid import UUID, uuid4
from uuid6 import uuid7
import numpy as np
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from src.crud import CollectID, CreateData, ReadData, UpdateData
from src.manager import ConnectionManager
from src.load_secrets import db_name, host, password, port, user
from src.models.dc_models import (
    ClientDataModel,
    CoordinateDataModel,
    MatchModel,
    PhysicalSimulatorModel,
    PlayerModel,
    ScoreModel,
    ShotInfoModel,
    StateModel,
    StoneCoordinateModel,
    TeamModel,
    TeamNameModel,
    TournamentModel,
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
from src.simulator import StoneSimulator
from src.database import engine
from src.basic_certification import BasicCertification

POSTGRES_DATABASE_URL = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
TEAM0_NAME = TeamNameModel(team_name="team0")
TEAM1_NAME = TeamNameModel(team_name="team1")
TEE_LINE = np.float32(38.405)

match_router = APIRouter()
logging.basicConfig(level=logging.DEBUG)
connect_manager = ConnectionManager()
Session = async_sessionmaker(
    autocommit=False, class_=AsyncSession, autoflush=True, bind=engine
)
session = Session()
security = HTTPBasic()
rest_router = APIRouter()
read_data = ReadData()
create_data = CreateData()
update_data = UpdateData()
stone_simulator = StoneSimulator()
basic_certification = BasicCertification()


def get_distance(
    team_number: int, x: np.float32, y: np.float32
) -> tuple[int, np.float32]:
    """calculate the distance of the stone from the tee

    Args:
        team_number (int): Team"0" or Team"1"
        x (np.float32): X-coordinate of stone
        y (np.float32): Y-coordinate of stone

    Returns:
        tuple[int, np.float32]: Team_number and distance of the stone from the tee
    """
    return (team_number, np.sqrt(x**2 + (y - TEE_LINE) ** 2))


def get_score(distance_list: List[tuple[int, np.float32]]) -> tuple[int, int]:
    """Get how many points either team scored

    Args:
        distance_list (List[tuple[int, np.float32]]): List containing the distance of each stone from the tee

    Returns:
        tuple[int, int]: The team that scored and the number of points scored
    """
    sort_distance_list = sorted(distance_list, key=lambda x: x[1])
    scored_team = sort_distance_list[0][0]
    score = 1

    for team, distance in sort_distance_list[1:]:
        if distance == sort_distance_list[0][1]:
            score += 1
        else:
            break
    return scored_team, score


def calculate_score(score_list: List[int]) -> int:
    """calculate the total score of the team

    Args:
        score_list (List[int]): List containing the scores for each end

    Returns:
        int: Total score of the team
    """
    score = 0
    for i in range(len(score_list)):
        score += score_list[i]
    return score


class BaseServer:
    @staticmethod
    @match_router.get("/get_match_id", response_model=UUID)
    async def get_match_id(client_data: ClientDataModel) -> UUID:
        """Send the match_id to the client and Set up the match data

        Args:
            client_data (ClientDataModel):
                    tournament: TournamentNameModel
                    simulator: PhysicalSimulatorNameModel
                    time_limit: int
                    extra_end_time_limit: int
                    standard_end_count: int
                    match_name: str

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
            winner_team=None,
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
            next_shot_team="5050f20f-cf97-4fb1-bbc1-f2c9052e0d17",
            created_at=datetime.now(),
            stone_coordinate=stone_coordinate,
        )
        # Create score data
        score = ScoreSchema(
            score_id=score_id, first_team_score=team_score, second_team_score=team_score
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
            first_team_name="first",
            second_team_name="second",
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
        await create_data.create_match_data(match_data, session)
        await create_data.create_state_data(state, session)

        return match_id


class DCServer:
    @staticmethod
    async def store_team_config(
        match_id: UUID, team_data: TeamModel
    ):
        """Store the team configuration data in the database

        Args:
            websocket (WebSocket): websocket (WebSocket): Connectors with connected client
            match_id (UUID): ID to identify this match
            team_number (int): Number of team0 or team1
        """

        if team_number == 0:
            await websocket.send_json(TEAM0_NAME.model_dump())
        elif team_number == 1:
            await websocket.send_json(TEAM1_NAME.model_dump())

        team_config_data = await websocket.receive_json()
        team_config_data = TeamModel(**team_config_data)
        if team_config_data.use_default_config:
            logging.info("Using default config")
            return 1

        player1_id = uuid4()
        player2_id = uuid4()
        player3_id = uuid4()
        player4_id = uuid4()
        team_id = uuid4()

        player1 = PlayerSchema(
            player_id=player1_id,
            team_id=team_id,
            max_velocity=team_config_data.player1.max_velocity,
            shot_dispersion_rate=team_config_data.player1.shot_dispersion_rate,
            player_name=team_config_data.player1.player_name,
        )
        player2 = PlayerSchema(
            player_id=player2_id,
            team_id=team_id,
            max_velocity=team_config_data.player2.max_velocity,
            shot_dispersion_rate=team_config_data.player2.shot_dispersion_rate,
            player_name=team_config_data.player2.player_name,
        )
        player3 = PlayerSchema(
            player_id=player3_id,
            team_id=team_id,
            max_velocity=team_config_data.player3.max_velocity,
            shot_dispersion_rate=team_config_data.player3.shot_dispersion_rate,
            player_name=team_config_data.player3.player_name,
        )
        player4 = PlayerSchema(
            player_id=player4_id,
            team_id=team_id,
            max_velocity=team_config_data.player4.max_velocity,
            shot_dispersion_rate=team_config_data.player4.shot_dispersion_rate,
            player_name=team_config_data.player4.player_name,
        )
        team_data = TeamSchema(
            player1_id=player1_id,
            player2_id=player2_id,
            player3_id=player3_id,
            player4_id=player4_id,
            team_name=team_config_data.team_name,
            player1=player1,
            player2=player2,
            player3=player3,
            player4=player4,
        )

        await create_data.create_team_data(team_data, session)
        if team_number == 0:
            await update_data.update_first_team(
                match_id, session, team_data
            )
            await update_data.update_next_shot_team(
                match_id, session, team_id
            )
        elif team_number == 1:
            await update_data.update_second_team(
                match_id, session, team_data
            )

    @staticmethod
    @match_router.get("/get_state_info")
    async def get_state_info(match_id: UUID):
        latest_state_data = read_data.read_latest_state_data(match_id, session)

    @staticmethod
    @match_router.post("/receive_shot_info")
    async def receive_shot_info(match_id: UUID, shot_info: ShotInfoModel):
        """Receive the shot information from the client

        Args:
            match_id (UUID): match_id
            shot_info (ShotInfoModel): shot information from the client
        """
        end_time: datetime = datetime.now()
        winmer_team: UUID = None

        # Get match data to know simulator and team_id
        match_data: MatchDataSchema = await read_data.read_match_data(match_id, session)

        # Get latest state data to know total shot number, stone coordinate and remaining time and so on.
        pre_state_data: StateSchema = await read_data.read_latest_state_data(
            match_id, session
        )
        # stone coordinate before receiving "shot_info"
        pre_stone_coordinate_data: StoneCoordinateSchema = (
            pre_state_data.stone_coordinate
        )
        # two client scores before receiving "shot_info"
        pre_score_data: ScoreSchema = pre_state_data.score
        # shot team which send this "shot_info"
        shot_team: UUID = pre_state_data.next_shot_team

        # total shot number at this time
        total_shot_number: int = pre_state_data.total_shot_number + 1
        player_number: int = int(total_shot_number / 4) + 1

        if team_number == 0:
            player_id = getattr(match_data, f"first_team_player{player_number}_id")
            team_id = match_data.first_team_id
        elif team_number == 1:
            player_id = getattr(match_data, f"second_team_plyaer{player_number}_id")
            team_id = match_data.second_team_id

        player_data = await read_data.read_player_data(player_id, session)
        dist_translation_velocity = np.max(
            [
                np.min([shot_info.translation_velocity, player_data.max_velocity])
                + np.random.normal(loc=0.0, scale=player_data.shot_dispersion_rate),
                0.0,
            ]
        )

        pre_end_time: datetime = pre_state_data.created_at
        time_diff: datetime = end_time - pre_end_time
        time_diff_seconds: float = time_diff.total_seconds()

    async def state_end_number_update(self, state_data: StateSchema) -> StateSchema:
        """

        Args:
            state_data (StateSchema): _description_

        Returns:
            StateSchema: _description_
        """
        stone_coordinate = self.reset_stone_coordinate()
        total_shot_number = 0

        state = StateSchema(
            state_id=uuid7(),
            winner_team=None,
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
            next_shot_team=self.next_shot_team_id,
            created_at=datetime.now(),
            stone_coordinate=stone_coordinate,
        )
        await create_data.create_state_data(state, session)

    def convert_stateschema_to_statemodel(self, state_data: StateSchema, used_time: float) -> StateModel:
        """Convert the StateSchema to the StateModel to send client

        Args:
            state_data (StateSchema): The latest state data of the match
            used_time (float): The time which you spend to think strategy

        Returns:
            StateModel: The latest state data of the match and is a type for transmission to the client
        """        
        winner_team_name = None
        state_model = StateModel(
            winner_team = winner_team_name,
            end_number = state_data.end_number,
            shot_number = state_data.shot_number,
            total_shot_number = state_data.total_shot_number,
            next_shot_team = next_shot_team,
            first_team_remaining_time = state_data.first_team_extra_end_remaining_time,
            second_team_remaining_time = state_data.second_team_extra_end_remaining_time,
            first_team_extra_remaining_time = state_data.first_team_extra_end_remaining_time,
            second_team_extra_remaining_time = state_data.second_team_extra_end_remaining_time,
            stone_coordinate = StoneCoordinateModel(
                stone_coordinate_id = state_data.stone_coordinate_id,
                stone_coordinate_data = {
                    team: [CoordinateDataModel(**coord) for coord in coords]
                    for team, coords in state_data.stone_coordinate.stone_coordinate_data.iten()
                }
            ),
            score = ScoreModel(
                first_team_score = state_data.score.first_team_score,
                second_team_score = state_data.score.second_team_score,
            )
        )
        return state_model
        

    def reset_stone_coordinate(self) -> StoneCoordinateSchema:
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

    def simulate_fcv1(
        self,
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

        simulated_stones_coordinate, flag, trajectory = self.stone_simulator.simulator(
            stone_position,
            total_shot_number,
            velocity_x,
            velocity_y,
            angular_velocity_sign,
            team_number,
            shot_per_team,
        )
        return simulated_stones_coordinate, flag, trajectory
