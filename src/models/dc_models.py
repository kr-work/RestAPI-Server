from pydantic import BaseModel
from enum import Enum
from uuid import UUID
from typing import Optional, Dict, List


class MatchNameModel(str, Enum):
    team0 = "team0"  # team0 is first attacker team at the first end
    team1 = "team1"  # team1 is sencond attacker team at the first end


class TournamentModel(BaseModel):
    tournament_id: UUID
    tournament_name: str


class TournamentNameModel(BaseModel):
    tournament_name: str


class PhysicalSimulatorNameModel(BaseModel):
    simulator_name: str


class PhysicalSimulatorModel(BaseModel):
    physical_simulator_id: UUID
    simulator_name: str


class CoordinateDataModel(BaseModel):
    x: float
    y: float

    class Config:
        from_attributes = True


class StoneCoordinateModel(BaseModel):
    stone_coordinate_data: Dict[str, List[CoordinateDataModel]]  # フラットなDict型

    class Config:
        from_attributes = True


class ScoreModel(BaseModel):
    team0_score: list
    team1_score: list

    class Config:
        from_attributes = True


class ShotInfoModel(BaseModel):
    translation_velocity: float
    angular_velocity_sign: str
    angular_velocity: float
    shot_angle: float


class StateModel(BaseModel):
    winner_team: str | None
    end_number: int
    shot_number: int
    total_shot_number: int
    next_shot_team: str | None
    first_team_remaining_time: float
    second_team_remaining_time: float
    first_team_extra_end_remaining_time: float
    second_team_extra_end_remaining_time: float
    stone_coordinate: Optional[StoneCoordinateModel] = None
    score: Optional[ScoreModel] = None

    class Config:
        from_attributes = True


class PlayerModel(BaseModel):
    max_velocity: float
    shot_dispersion_rate: float
    player_name: str


class TeamModel(BaseModel):
    use_default_config: bool
    team_name: str
    player1: PlayerModel
    player2: PlayerModel
    player3: PlayerModel
    player4: PlayerModel


class ClientDataModel(BaseModel):
    tournament: TournamentNameModel
    simulator: PhysicalSimulatorNameModel
    time_limit: int
    extra_end_time_limit: int
    standard_end_count: int
    match_name: str


class MatchModel(BaseModel):
    match_id: UUID
    time_limit: int
    extra_end_time_limit: int
    standard_end_count: int
    match_name: str
    score: Optional[ScoreModel] = None
    simulator: Optional[PhysicalSimulatorModel] = None
    tournament: Optional[TournamentModel] = None
