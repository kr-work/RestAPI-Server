import asyncio
import json
import logging
from datetime import datetime
from typing import List
from uuid import UUID, uuid4
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from uuid6 import uuid7
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from src.crud import CreateData, ReadData, UpdateData
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
from src.database import engine
from src.shared_queue import SharedList
from src.match_sync_manager import MatchSyncManager
from src.simulator import StoneSimulator

POSTGRES_DATABASE_URL = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
TEAM0_NAME = TeamNameModel(team_name="team0")
TEAM1_NAME = TeamNameModel(team_name="team1")
TEE_LINE = np.float32(38.405)

match_router = APIRouter()
logging.basicConfig(level=logging.DEBUG)
connect_manager = ConnectionManager()
shared_list = SharedList()
Session = async_sessionmaker(
    autocommit=False, class_=AsyncSession, autoflush=True, bind=engine
)
session = Session()
match_sync_manager = MatchSyncManager()


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
        try:
            flag = await shared_list.check_id(match_id, increment_count=2)
        except asyncio.TimeoutError:
            logging.error("Timeout reached while waiting for match_id")

        return match_id

    @staticmethod
    @match_router.websocket("/ws/connect/{match_id}/{team_number}")
    async def dc(websocket: WebSocket, match_id: UUID, team_number: int):
        """Connect to client and start the game

        Args:
            websocket (WebSocket): websocket (WebSocket): Connectors with connected client
            match_id (UUID): ID to identify this match
            team_number (int): Number of team0 or team1
        """
        await connect_manager.connect(websocket, match_id)
        is_disconnected = False  # Disconnection flag added

        try:
            logging.info("connected")
            while len(connect_manager.active_connections[match_id]) < 2:
                await asyncio.sleep(0.5)
            logging.info("2 clients connected")

            try:
                stone_simulator = StoneSimulator()
            except Exception as e:
                logging.error(f"Error in creating simulator: {e}")
            logging.info("Simulator created")
            match_condition = await match_sync_manager.get_condition_and_ready_count(
                match_id
            )
            LocalSession = async_sessionmaker(
                autocommit=False, class_=AsyncSession, autoflush=True, bind=engine
            )
            local_session = LocalSession()

            dc_server = DCServer(local_session)
            # Store the team configuration data in the database or use the default configuration
            await dc_server.store_team_config(websocket, match_id, team_number)

            match_data = await ReadData.read_match_data(match_id, local_session)
            state_data = await ReadData.read_latest_state_data(match_id, local_session)

            # Set the each team's ID and standard end count
            dc_server.set(
                match_data.first_team_id,
                match_data.second_team_id,
                match_data.standard_end_count,
                stone_simulator,
            )

            remaining_time = match_data.time_limit
            send_flag = True

            first_team_id = match_data.first_team_id
            second_team_id = match_data.second_team_id

            if team_number == 0:
                team_id = first_team_id
            elif team_number == 1:
                team_id = second_team_id
            else:
                raise ValueError("Invalid team_number")

            # Start the game
            while True:
                async with match_condition:
                    await match_sync_manager.increment_ready_count(match_id)
                    while await match_sync_manager.get_ready_count(match_id) < 2:
                        await match_condition.wait()
                    match_condition.notify_all()

                if send_flag:
                    state_data = await ReadData.read_latest_state_data(
                        match_id, local_session
                    )

                # if state_data.total_shot_number < 16:
                assert state_data is not None
                assert state_data.score is not None
                next_shot_team_id = state_data.next_shot_team
                game_over_flag = await dc_server.send_state_data(
                    websocket, remaining_time, state_data
                )
                if game_over_flag:
                    assert state_data.winner_team is not None
                    break

                start_time = datetime.now()

                if state_data.total_shot_number < 16:
                    if str(next_shot_team_id) == str(team_id):
                        remaining_time = await dc_server.receive_shot_info(
                            websocket,
                            match_data,
                            state_data,
                            team_number,
                            start_time,
                        )

                    send_flag = await shared_list.check_id(match_id)
                    # logging.info(f"team_number: {team_number}")

                elif state_data.total_shot_number == 16:
                    if str(next_shot_team_id) == str(team_id):
                        await dc_server.state_end_number_update(state_data)

                    send_flag = await shared_list.check_id(match_id)
                await match_sync_manager.reset_ready_count(match_id)
            is_disconnected = True  # Set disconnection flag
            logging.info(f"WebSocket close: {match_id}")
            connect_manager.disconnect(websocket, match_id)

        except WebSocketDisconnect:
            is_disconnected = True  # Set disconnection flag
            logging.error(f"WebSocket disconnected for match_id: {match_id}")
            connect_manager.disconnect(websocket, match_id)
        except Exception as e:
            print(e)
            logging.error(f"Unexpected error: {e}")
            connect_manager.disconnect(websocket, match_id)
        finally:
            # Close connection only if it's still connected
            await match_sync_manager.cleanup(match_id)
            if not is_disconnected:
                await websocket.close()


class DCServer:
    def __init__(self, local_session: AsyncSession):
        """Set the next shot team name to team0"""
        self.next_shot_team_name = "team0"
        self.winner_team_id = None
        self.winner_team_name = None
        self.create_data = CreateData()
        self.update_data = UpdateData()
        self.local_session = local_session

    def set(
        self,
        first_team_id: UUID,
        second_team_id: UUID,
        standard_end_count: int,
        stone_simulator: StoneSimulator,
    ):
        """Set the each team's ID

        Args:
            first_team_id (UUID): Set the first team's(team0) ID
            second_team_id (UUID): Set the second team's(team1) ID
            standard_end_count (int): Set the standard end count of the match
            stone_simulator (StoneSimulator): Set the stone simulator(fcv1)
        """
        self.first_team_id = first_team_id
        self.second_team_id = second_team_id
        self.next_shot_team_id = first_team_id
        self.standard_end_count = standard_end_count
        self.stone_simulator = stone_simulator

    def convert_stateschema_to_statemodel(
        self, state_data: StateSchema, remaining_time: float
    ) -> StateModel:
        """Convert the StateSchema to the StateModel

        Args:
            state_data (StateSchema): The latest state data of the match

        Returns:
            StateModel: The latest state data of the match and is a type for transmission to the client
        """
        if state_data.winner_team == self.first_team_id:
            self.winner_team_name = "team0"
            state_data.next_shot_team = None
        elif state_data.winner_team == self.second_team_id:
            self.winner_team_name = "team1"
            state_data.next_shot_team = None

        if state_data.next_shot_team == self.first_team_id:
            self.next_shot_team = "team0"
        elif state_data.next_shot_team == self.second_team_id:
            self.next_shot_team = "team1"

        state_model = StateModel(
            winner_team=self.winner_team_name,
            end_number=state_data.end_number,
            shot_number=state_data.shot_number,
            total_shot_number=state_data.total_shot_number,
            next_shot_team=self.next_shot_team,
            first_team_remaining_time=state_data.first_team_remaining_time,
            second_team_remaining_time=state_data.second_team_remaining_time,
            first_team_extra_end_remaining_time=state_data.first_team_extra_end_remaining_time,
            second_team_extra_end_remaining_time=state_data.second_team_extra_end_remaining_time,
            stone_coordinate=StoneCoordinateModel(
                stone_coordinate_id=state_data.stone_coordinate.stone_coordinate_id,
                stone_coordinate_data={
                    team: [CoordinateDataModel(**coord) for coord in coords]
                    for team, coords in state_data.stone_coordinate.stone_coordinate_data.items()
                }
                if state_data.stone_coordinate
                else None,
            ),
            score=ScoreModel(
                first_team_score=state_data.score.first_team_score,
                second_team_score=state_data.score.second_team_score,
            ),
        )
        return state_model

    async def store_team_config(
        self, websocket: WebSocket, match_id: UUID, team_number: int
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

        await self.create_data.create_team_data(team_data, self.local_session)
        if team_number == 0:
            await self.update_data.update_first_team(
                match_id, self.local_session, team_data
            )
            await self.update_data.update_next_shot_team(
                match_id, self.local_session, team_id
            )
        elif team_number == 1:
            await self.update_data.update_second_team(
                match_id, self.local_session, team_data
            )

    async def send_state_data(
        self, websocket: WebSocket, remaining_time: float, state_data: StateSchema
    ) -> bool:
        """Send the state data and check if the game is over

        Args:
            websocket (WebSocket): Connectors with connected client
            match_id (UUID): _ID to identify this match
            state_data (StateSchema): The latest state data of the match

        Returns:
            bool: Return True if the game is over
        """
        game_over_flag = False

        if state_data.winner_team is not None:
            game_over_flag = True

        state_data_to_send: StateModel = self.convert_stateschema_to_statemodel(
            state_data, remaining_time
        )
        state_data_to_send_dict = state_data_to_send.model_dump()
        await websocket.send_json(state_data_to_send_dict)
        return game_over_flag

    async def receive_shot_info(
        self,
        websocket: WebSocket,
        match_data: MatchDataSchema,
        state_data: StateSchema,
        team_number: int,
        start_time: datetime,
    ):
        """Receive the shot information from the client and simulate the shot

        Args:
            websocket (WebSocket): Connectors with connected client
            match_data (MatchDataSchema): _description_
            state_data (StateSchema): _description_
            team_number (int): Number of team0 or team1
            start_time (datetime): Time when the shot is started
        """

        # Receive the shot information from the client
        shot_info: ShotInfoModel = await websocket.receive_json()
        end_time: datetime = datetime.now()
        diff_time: datetime = end_time - start_time
        diff_time: float = diff_time.total_seconds()

        # logging.info(f"remaining_time: {remaining_time}")
        shot_info = ShotInfoModel(**shot_info)

        # Store the shot information in the database
        shot_info_data = await self.convert_shot_info(
            shot_info, match_data, state_data, team_number
        )

        total_shot_number = state_data.total_shot_number
        shot_per_team = state_data.shot_number
        end_number = state_data.end_number
        first_team_remaining_time = state_data.first_team_remaining_time
        second_team_remaining_time = state_data.second_team_remaining_time
        first_team_extra_end_remaining_time = (
            state_data.first_team_extra_end_remaining_time
        )
        second_team_extra_end_remaining_time = (
            state_data.second_team_extra_end_remaining_time
        )

        if match_data.simulator.simulator_name == "fcv1":
            simulated_stones_coordinate, flag, trajectory = self.simulate_fcv1(
                shot_info, state_data, total_shot_number, shot_per_team, team_number
            )

        stone_coordinate = self.convert_stone_coordinate_data(
            simulated_stones_coordinate
        )

        total_shot_number += 1  # Increment the total shot number
        shot_id = uuid7() if total_shot_number != 16 else None

        if team_number == 0:
            self.next_shot_team_name = "team1"
            if end_number <= match_data.standard_end_count - 1:
                first_team_remaining_time -= diff_time
            else:
                first_team_extra_end_remaining_time -= diff_time
        elif team_number == 1:
            self.next_shot_team_name = "team0"
            if end_number <= match_data.standard_end_count - 1:
                second_team_remaining_time -= diff_time
            else:
                second_team_extra_end_remaining_time -= diff_time

        # Get the team_id of the next shot team
        if self.next_shot_team_name == "team0":
            self.next_shot_team_id = match_data.first_team_id
        elif self.next_shot_team_name == "team1":
            self.next_shot_team_id = match_data.second_team_id

        if total_shot_number == 16:
            distance_list = []
            team0_score = state_data.score.first_team_score
            team1_score = state_data.score.second_team_score
            for (
                team,
                stones,
            ) in state_data.stone_coordinate.stone_coordinate_data.items():
                for stone in stones:
                    distance_list.append(get_distance(team, stone["x"], stone["y"]))
            scored_team, score = get_score(distance_list)
            self.next_shot_team_name = f"team{scored_team}"
            logging.info(f"state_data.end_number: {state_data.end_number}")

            if state_data.end_number <= match_data.standard_end_count - 1:
                if scored_team == "team0":
                    team0_score[state_data.end_number] = score
                    team1_score[state_data.end_number] = 0
                elif scored_team == "team1":
                    team0_score[state_data.end_number] = 0
                    team1_score[state_data.end_number] = score

                score_data = ScoreSchema(
                    score_id=state_data.score_id,
                    first_team_score=team0_score,
                    second_team_score=team1_score,
                )
                logging.info(f"score_data: {score_data}")
                # Update the score data at the end of the "end"
                await self.update_data.update_score(score_data, self.local_session)

            if state_data.end_number == match_data.standard_end_count - 1:
                score_diff = calculate_score(
                    state_data.score.first_team_score
                ) - calculate_score(state_data.score.second_team_score)
                if score_diff > 0:
                    self.winner_team_id = self.first_team_id
                    self.next_shot_team = None
                elif score_diff < 0:
                    self.winner_team_id = self.second_team_id
                    self.next_shot_team = None
                else:
                    pass

            elif state_data.end_number > match_data.standard_end_count - 1:
                logging.info(f"state_data.end_number: {state_data.end_number}")
                if scored_team == "team0":
                    self.winner_team_id = self.first_team_id
                    self.next_shot_team = None
                elif scored_team == "team1":
                    self.winner_team_id = self.second_team_id
                    self.next_shot_team = None

        state = StateSchema(
            state_id=shot_info_data.post_shot_state_id,
            winner_team=self.winner_team_id,
            match_id=match_data.match_id,
            end_number=end_number,
            shot_number=int(total_shot_number / 2),
            total_shot_number=total_shot_number,
            first_team_remaining_time=first_team_remaining_time,
            second_team_remaining_time=second_team_remaining_time,
            first_team_extra_end_remaining_time=first_team_extra_end_remaining_time,
            second_team_extra_end_remaining_time=second_team_extra_end_remaining_time,
            stone_coordinate_id=stone_coordinate.stone_coordinate_id,
            score_id=state_data.score_id,
            shot_id=shot_id,
            next_shot_team=self.next_shot_team_id,
            created_at=datetime.now(),
            stone_coordinate=stone_coordinate,
        )
        # await shared_list.check_contains_id(match_id)

        await self.create_data.create_shot_info_data(shot_info_data, self.local_session)
        await self.create_data.create_state_data(state, self.local_session)

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
        await self.create_data.create_state_data(state, self.local_session)

    def convert_stone_coordinate_data(
        self, simulated_stones_coordinate: np.ndarray
    ) -> StoneCoordinateSchema:
        """Convert the simulated stone coordinate to the StoneCoordinateSchema

        Args:
            simulated_stones_coordinate (np.ndarray): Stone's coordinate data after calculation in simulator

        Returns:
            StoneCoordinateSchema: Data converted from simulated stone coordinate data into a form that can be stored in a database
        """
        stone_coordinates_data = {
            "team0": [
                {
                    "x": simulated_stones_coordinate[0],
                    "y": simulated_stones_coordinate[1],
                },
                {
                    "x": simulated_stones_coordinate[2],
                    "y": simulated_stones_coordinate[3],
                },
                {
                    "x": simulated_stones_coordinate[4],
                    "y": simulated_stones_coordinate[5],
                },
                {
                    "x": simulated_stones_coordinate[6],
                    "y": simulated_stones_coordinate[7],
                },
                {
                    "x": simulated_stones_coordinate[8],
                    "y": simulated_stones_coordinate[9],
                },
                {
                    "x": simulated_stones_coordinate[10],
                    "y": simulated_stones_coordinate[11],
                },
                {
                    "x": simulated_stones_coordinate[12],
                    "y": simulated_stones_coordinate[13],
                },
                {
                    "x": simulated_stones_coordinate[14],
                    "y": simulated_stones_coordinate[15],
                },
            ],
            "team1": [
                {
                    "x": simulated_stones_coordinate[16],
                    "y": simulated_stones_coordinate[17],
                },
                {
                    "x": simulated_stones_coordinate[18],
                    "y": simulated_stones_coordinate[19],
                },
                {
                    "x": simulated_stones_coordinate[20],
                    "y": simulated_stones_coordinate[21],
                },
                {
                    "x": simulated_stones_coordinate[22],
                    "y": simulated_stones_coordinate[23],
                },
                {
                    "x": simulated_stones_coordinate[24],
                    "y": simulated_stones_coordinate[25],
                },
                {
                    "x": simulated_stones_coordinate[26],
                    "y": simulated_stones_coordinate[27],
                },
                {
                    "x": simulated_stones_coordinate[28],
                    "y": simulated_stones_coordinate[29],
                },
                {
                    "x": simulated_stones_coordinate[30],
                    "y": simulated_stones_coordinate[31],
                },
            ],
        }

        stone_coordinate = StoneCoordinateSchema(
            stone_coordinate_id=uuid7(),
            stone_coordinate_data=json.dumps(stone_coordinates_data),
        )
        return stone_coordinate

    async def convert_shot_info(
        self,
        shot_info: ShotInfoModel,
        match_data: MatchDataSchema,
        state_data: StateSchema,
        team_number: int,
    ) -> ShotInfoSchema:
        """Convert the shot information to the ShotInfoSchema and store it in the database

        Args:
            shot_info (ShotInfoModel): Shot information from the client
            match_data (MatchDataSchema): Match data
            state_data (StateSchema): The latest state data of the match
            team_number (int): Team"0" or Team"1"

        Returns:
            ShotInfoSchema: Data converted from shot information into a form that can be stored in a database
        """
        total_shot_number = state_data.total_shot_number
        player_number = int(total_shot_number / 4) + 1

        if team_number == 0:
            player_id = getattr(match_data, f"first_team_player{player_number}_id")
            team_id = match_data.first_team_id
        elif team_number == 1:
            player_id = getattr(match_data, f"second_team_player{player_number}_id")
            team_id = match_data.second_team_id

        player_data = await ReadData.read_player_data(player_id, self.local_session)
        dist_translation_velocity = np.max(
            [
                np.min([shot_info.translation_velocity, player_data.max_velocity])
                + np.random.normal(loc=0.0, scale=player_data.shot_dispersion_rate),
                0.0,
            ]
        )
        dist_shot_angle = shot_info.shot_angle + np.random.normal(
            loc=0.0, scale=player_data.shot_dispersion_rate
        )

        shot_info_data = ShotInfoSchema(
            shot_id=state_data.shot_id,
            player_id=player_id,
            team_id=team_id,
            trajectory_id=uuid7(),
            pre_shot_state_id=state_data.state_id,
            post_shot_state_id=uuid7(),
            translation_velocity=dist_translation_velocity,
            angular_velocity_sign=shot_info.angular_velocity_sign,
            angular_velocity=shot_info.angular_velocity,
            shot_angle=dist_shot_angle,
        )
        return shot_info_data

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

    # async def get_next_shot_team_id(match_data: MatchDataSchema ,player_number: int, next_shot_team: str):
