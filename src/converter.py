import json
from datetime import datetime
from typing import List
import numpy as np

# import database
from uuid import UUID, uuid4
from uuid6 import uuid7

from src.models.dc_models import (
    MatchModel,
    ScoreModel,
    ShotInfoModel,
    StateModel,
    CoordinateDataModel,
    StoneCoordinateModel,
)
from src.models.schema_models import (
    MatchDataSchema,
    PhysicalSimulatorSchema,
    ScoreSchema,
    ShotInfoSchema,
    StateSchema,
    StoneCoordinateSchema,
    TournamentSchema,
    TrajectorySchema,
)

class DataConverter:
    """This class is used to convert data between different formats."""

    def convert_stateschema_to_statemodel(self, match_data: MatchDataSchema, state_data: StateSchema) -> StateModel:
        """Convert the StateSchema to the StateModel to send client
        Args:
            match_data (MatchDataSchema): The match data of the match
            state_data (StateSchema): The latest state data of the match
        Returns:
            StateModel: The state data of the match and is a type for transmission to the client
        """   
        winner_team_name = None
        next_shot_team = None
        if state_data.winner_team_id is not None:
            winner_team_id = state_data.winner_team_id
            winner_team_name = (
                "team0"
                if winner_team_id == match_data.first_team_id
                else "team1"
            )

        if state_data.next_shot_team_id is not None:
            next_shot_team_id = state_data.next_shot_team_id
            next_shot_team = (
                "team0"
                if next_shot_team_id == match_data.first_team_id
                else "team1"
            )
        
        state_model = StateModel(
            winner_team=winner_team_name,
            first_team_name = match_data.first_team_name,
            second_team_name = match_data.second_team_name,
            end_number = state_data.end_number,
            shot_number = state_data.shot_number,
            total_shot_number = state_data.total_shot_number,
            next_shot_team = next_shot_team,
            first_team_remaining_time = state_data.first_team_extra_end_remaining_time,
            second_team_remaining_time = state_data.second_team_extra_end_remaining_time,
            first_team_extra_end_remaining_time = state_data.first_team_extra_end_remaining_time,
            second_team_extra_end_remaining_time = state_data.second_team_extra_end_remaining_time,
            stone_coordinate = StoneCoordinateModel(
                stone_coordinate_data = {
                    team: [CoordinateDataModel(**coord) for coord in coords]
                    for team, coords in state_data.stone_coordinate.stone_coordinate_data.items()
                }
            ),
            score = ScoreModel(
                team0_score = state_data.score.team0_score,
                team1_score = state_data.score.team1_score,
            )
        )
        return state_model
    
    def convert_stonecoordinate_to_stonecoordinateschema(self, stone_coordinate_data: StoneCoordinateModel) -> StoneCoordinateSchema:
        """Convert the StoneCoordinateModel to the StoneCoordinateSchema to send client

        Args:
            stone_coordinate_data (StoneCoordinateModel): The stone coordinate data of the match

        Returns:
            StoneCoordinateSchema: The stone coordinate data of the match and is a type for transmission to the client
        """
        stones_data = json.loads(stone_coordinate_data.model_dump_json())
        stones_data = stones_data["stone_coordinate_data"]
        stones_data = json.dumps(stones_data)
        stone_coordinate_schema = StoneCoordinateSchema(
            stone_coordinate_id = uuid7(),
            stone_coordinate_data = stones_data
        )
        return stone_coordinate_schema
        