from uuid6 import uuid7

from src.models.dc_models import (
    ScoreModel,
    StateModel,
    CoordinateDataModel,
    StoneCoordinateModel,
    ShotInfoModel,
    PowerPlayEndModel,
    MixDoublesSettingsModel,
    GameModeModel,
)
from src.models.schema_models import (
    MatchDataSchema,
    StateSchema,
    StoneCoordinateSchema,
)


class DataConverter:
    """This class is used to convert data between different formats."""

    def convert_stateschema_to_statemodel(
        self,
        match_data: MatchDataSchema,
        state_data: StateSchema,
        shot_info_data=None,
        mix_doubles_end_setup=None,
    ) -> StateModel:
        """Convert the StateSchema to the StateModel to send client

        Args:
            match_data (MatchDataSchema): The match data of the match
            state_data (StateSchema): The latest state data of the match

        Returns:
            StateModel: The state data of the match and is a type for transmission to the client
        """
        if match_data is None:
            raise ValueError("match_data is required")

        winner_team_name: str = None
        next_shot_team: str = None
        if state_data.winner_team_id is not None:
            winner_team_id = state_data.winner_team_id
            winner_team_name = (
                "team0" if winner_team_id == match_data.first_team_id else "team1"
            )

        if state_data.next_shot_team_id is not None:
            next_shot_team_id = state_data.next_shot_team_id
            next_shot_team = (
                "team0" if next_shot_team_id == match_data.first_team_id else "team1"
            )

        last_move = None
        if shot_info_data is not None:
            last_move = ShotInfoModel(
                translational_velocity=shot_info_data.translational_velocity,
                angular_velocity=shot_info_data.angular_velocity,
                shot_angle=shot_info_data.shot_angle,
            )

        # Determine if it is pre-end setup for mixed doubles
        is_pre_end_setup = match_data.game_mode == GameModeModel.mix_doubles.value and state_data.next_shot_team_id is None

        shot_number = state_data.shot_number
        total_shot_number = state_data.total_shot_number
        # If it is pre-end setup, set shot_number and total_shot_number to None
        if is_pre_end_setup:
            shot_number = None
            total_shot_number = None

        state_model: StateModel = StateModel(
            winner_team=winner_team_name,
            first_team_name=match_data.first_team_name,
            second_team_name=match_data.second_team_name,
            end_number=state_data.end_number,
            shot_number=shot_number,
            total_shot_number=total_shot_number,
            next_shot_team=next_shot_team,
            first_team_remaining_time=state_data.first_team_remaining_time,
            second_team_remaining_time=state_data.second_team_remaining_time,
            first_team_extra_end_remaining_time=state_data.first_team_extra_end_remaining_time,
            second_team_extra_end_remaining_time=state_data.second_team_extra_end_remaining_time,
            mix_doubles_settings=(
                MixDoublesSettingsModel(
                    end_setup_team=(
                        "team0"
                        if (
                            (
                                mix_doubles_end_setup.end_setup_team_id
                                if mix_doubles_end_setup is not None
                                else match_data.first_team_id
                            )
                            == match_data.first_team_id
                        )
                        else "team1"
                    ),
                    positioned_stones_pattern=int(
                        match_data.mix_doubles_settings.positioned_stones_pattern
                    ),
                    power_play_end=PowerPlayEndModel(
                        team0=match_data.mix_doubles_settings.team0_power_play_end,
                        team1=match_data.mix_doubles_settings.team1_power_play_end,
                    ),
                )
                if match_data.mix_doubles_settings is not None
                else None
            ),
            last_move=last_move,
            stone_coordinate=StoneCoordinateModel(
                data={
                    team: [CoordinateDataModel(**coord) for coord in coords]
                    for team, coords in state_data.stone_coordinate.data.items()
                }
            ),
            score=ScoreModel(
                team0=state_data.score.team0,
                team1=state_data.score.team1,
            ),
        )
        return state_model

    def convert_stonecoordinate_to_stonecoordinateschema(
        self, stone_coordinate_data: StoneCoordinateModel
    ) -> StoneCoordinateSchema:
        """Convert the StoneCoordinateModel to the StoneCoordinateSchema to send client

        Args:
            stone_coordinate_data (StoneCoordinateModel): The stone coordinate data of the match

        Returns:
            StoneCoordinateSchema: The stone coordinate data of the match and is a type for transmission to the client
        """
        stone_coordinate_schema: StoneCoordinateSchema = StoneCoordinateSchema(
            stone_coordinate_id=uuid7(), data=stone_coordinate_data.data
        )
        return stone_coordinate_schema
