from pydantic import BaseModel, Json
from typing import Optional
from uuid import UUID
from datetime import datetime


class TournamentSchema(BaseModel):
    tournament_id: UUID
    tournament_name: str

    class Config:
        from_attributes = True


class PhysicalSimulatorSchema(BaseModel):
    physical_simulator_id: UUID
    simulator_name: str

    class Config:
        from_attributes = True


class PlayerSchema(BaseModel):
    player_id: UUID
    team_id: UUID
    max_velocity: float
    shot_dispersion_rate: float
    player_name: str

    class Config:
        from_attributes = True


class TrajectorySchema(BaseModel):
    trajectory_id: UUID
    trajectory_data: Json


class StoneCoordinateSchema(BaseModel):
    stone_coordinate_id: UUID
    stone_coordinate_data: Json

    class Config:
        from_attributes = True


class ScoreSchema(BaseModel):
    score_id: UUID
    first_team_score: list
    second_team_score: list

    class Config:
        from_attributes = True


class ShotInfoSchema(BaseModel):
    shot_id: UUID
    player_id: UUID
    team_id: UUID
    trajectory_id: UUID
    pre_shot_state_id: UUID
    post_shot_state_id: UUID
    velocity_x: float
    velocity_y: float
    angular_velocity_sign: int

    class Config:
        from_attributes = True

class StateSchema(BaseModel):
    state_id: UUID
    winner_team_id: UUID | None
    match_id: UUID
    end_number: int
    shot_number: int
    total_shot_number: int
    first_team_remaining_time: float
    second_team_remaining_time: float
    first_team_extra_end_remaining_time: float
    second_team_extra_end_remaining_time: float
    stone_coordinate_id: UUID
    score_id: UUID
    shot_id: UUID | None
    next_shot_team_id: UUID | None
    created_at: datetime
    stone_coordinate: Optional[StoneCoordinateSchema] = None
    score: Optional[ScoreSchema] = None

    class Config:
        from_attributes = True


class MatchDataSchema(BaseModel):
    match_id: UUID
    first_team_name: str | None
    second_team_name: str | None
    first_team_id: UUID
    first_team_player1_id: UUID
    first_team_player2_id: UUID
    first_team_player3_id: UUID
    first_team_player4_id: UUID
    second_team_id: UUID
    second_team_player1_id: UUID
    second_team_player2_id: UUID
    second_team_player3_id: UUID
    second_team_player4_id: UUID
    winner_team_id: UUID | None
    score_id: UUID
    time_limit: int
    extra_end_time_limit: int
    standard_end_count: int
    physical_simulator_id: UUID
    tournament_id: UUID
    match_name: str
    created_at: datetime
    started_at: datetime
    score: Optional[ScoreSchema] = None
    tournament: Optional[TournamentSchema] = None
    simulator: Optional[PhysicalSimulatorSchema] = None

    class Config:
        from_attributes = True


class TeamSchema(BaseModel):
    player1_id: UUID
    player2_id: UUID
    player3_id: UUID
    player4_id: UUID
    team_name: str
    player1: Optional[PlayerSchema] = None
    player2: Optional[PlayerSchema] = None
    player3: Optional[PlayerSchema] = None
    player4: Optional[PlayerSchema] = None



