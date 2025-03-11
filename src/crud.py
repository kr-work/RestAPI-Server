# import database
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import joinedload
from typing import List
import logging
import json

from src.models.schema_models import (
    MatchDataSchema,
    ScoreSchema,
    StateSchema,
    StoneCoordinateSchema,
    TrajectorySchema,
    TournamentSchema,
    PhysicalSimulatorSchema,
    PlayerSchema,
    TeamSchema,
    ShotInfoSchema,
)
from src.models.schemas import (
    Base,
    Match,
    Score,
    State,
    StoneCoordinate,
    Trajectory,
    Tournament,
    PhysicalSimulator,
    Player,
    ShotInfo,
)
from uuid import UUID


class UpdateData:
    @staticmethod
    async def update_first_team(match_id: UUID, session: AsyncSession, first_team: TeamSchema):
        """Update match table with first team data

        Args:
            match_id (UUID): To identify the match
            first_team (TeamSchema): First attack at the first end
        """
        async with session:
            try:
                stmt = select(Match).where(Match.match_id == match_id)
                result = await session.execute(stmt)
                result = result.scalars().first()

                if result is None:
                    return False

                result.first_team_name = first_team.team_name
                result.first_team_player1_id = first_team.player1_id
                result.first_team_player2_id = first_team.player2_id
                result.first_team_player3_id = first_team.player3_id
                result.first_team_player4_id = first_team.player4_id
                await session.commit()
            except Exception as e:
                logging.error(f"Failed to update first team data: {e}")

    @staticmethod
    async def update_second_team(match_id: UUID, session: AsyncSession, second_team: TeamSchema):
        """Update match table with second team data

        Args:
            match_id (UUID): To identify the match
            second_team (TeamSchema): Second attack at the first end
        """
        async with session:
            try:
                stmt = select(Match).where(Match.match_id == match_id)
                result = await session.execute(stmt)
                result = result.scalars().first()

                if result is None:
                    return False

                result.second_team_name = second_team.team_name
                result.second_team_player1_id = second_team.player1_id
                result.second_team_player2_id = second_team.player2_id
                result.second_team_player3_id = second_team.player3_id
                result.second_team_player4_id = second_team.player4_id
                await session.commit()
            except Exception as e:
                logging.error(f"Failed to update second team data: {e}")

    @staticmethod
    async def update_winner_and_next_shot_team(state_id: UUID, session: AsyncSession, winner_team: UUID):
        """Update state table with winner team and next shot team

        Args:
            state_id (UUID): To identify the state
            winner_team (UUID): Winner team of the game
        """
        async with session:
            try:
                stmt = select(State).where(State.state_id == state_id)
                result = await session.execute(stmt)
                result = result.scalars().first()

                if result is None:
                    return False

                result.winner_team = winner_team
                result.next_shot_team = None
                await session.commit()
            except Exception as e:
                logging.error(f"Failed to update winner team data: {e}")

    @staticmethod
    async def update_next_shot_team(match_id: UUID, session: AsyncSession, next_shot_team: UUID):
        """

        Args:
            match_id (UUID): To identify the latest state
            next_shot_team (UUID): Next shot team id
        """
        async with session:
            try:
                stmt = (
                    select(State)
                    .where(State.match_id == match_id)
                    .order_by(desc(State.created_at))
                    .limit(1)
                )
                result = await session.execute(stmt)
                result = result.scalars().first()

                if result is None:
                    return False

                result.next_shot_team = next_shot_team
                await session.commit()
            except Exception as e:
                logging.error(f"Failed to update next shot team data: {e}")

    @staticmethod
    async def update_score(score: ScoreSchema, session: AsyncSession):
        """Update score table with new score

        Args:
            score (ScoreSchema): New score data
        """
        async with session:
            try:
                stmt = select(Score).where(Score.score_id == score.score_id)
                result = await session.execute(stmt)
                result = result.scalars().first()

                if result is None:
                    return False

                result.first_team_score = score.first_team_score
                result.second_team_score = score.second_team_score
                await session.commit()
            except Exception as e:
                logging.error(f"Failed to update score data: {e}")


class ReadData:
    @staticmethod
    async def read_match_data(match_id: UUID, session: AsyncSession) -> MatchDataSchema:
        """Read match data and score, tournament, simulator data from database

        Args:
            match_id (UUID): To identify the match

        Returns:
            MatchDataSchema: Match data with score, tournament, simulator data
        """
        async with session:
            try:
                stmt = (
                    select(Match)
                    .where(Match.match_id == match_id)
                    .options(
                        joinedload(Match.score),
                        joinedload(Match.tournament),
                        joinedload(Match.simulator),
                    )
                )
                result = await session.execute(stmt)
                result = result.scalars().first()

                if result is None:
                    return None

                match_data = MatchDataSchema.model_validate(result)
                return match_data
            except Exception as e:
                logging.error(f"Failed to read match data: {e}")

    @staticmethod
    async def read_state_data(state_id: UUID, session: AsyncSession) -> StateSchema:
        """Read specific state data and stone coordinate data from database

        Args:
            state_id (UUID): To get the specific state data

        Returns:
            StateSchema: State data with stone coordinate data
        """
        async with session:
            try:
                stmt = (
                    select(State)
                    .options(joinedload(State.stone_coordinate))
                    .where(State.state_id == state_id)
                )
                result = await session.execute(stmt)
                result = result.scalars().first()

                if result is None:
                    return None

                stone_coordinate_data = None
                if result.stone_coordinate:
                    stone_coordinate_data = StoneCoordinateSchema(
                        stone_coordinate_id=result.stone_coordinate.stone_coordinate_id,
                        stone_coordinate_data=json.dumps(
                            result.stone_coordinate.stone_coordinate_data
                        ),
                    )

                state_data = StateSchema(
                    state_id=result.state_id,
                    match_id=result.match_id,
                    end_number=result.end_number,
                    shot_number=result.shot_number,
                    total_shot_number=result.total_shot_number,
                    first_team_remaining_time=result.first_team_remaining_time,
                    second_team_remaining_time=result.second_team_remaining_time,
                    first_team_extra_end_remaining_time=result.first_team_extra_end_remaining_time,
                    second_team_extra_end_remaining_time=result.second_team_extra_end_remaining_time,
                    stone_coordinate_id=result.stone_coordinate_id,
                    shot_id=result.shot_id,
                    next_shot_team=result.next_shot_team,
                    created_at=result.created_at,
                    stone_coordinate=stone_coordinate_data,
                )
                return state_data
            except Exception as e:
                logging.error(f"Failed to read state data: {e}")

    @staticmethod
    async def read_latest_state_data(match_id: UUID, session: AsyncSession) -> StateSchema:
        """Read the latest state data and stone coordinate data from database

        Args:
            match_id (UUID): To identify the latest state

        Returns:
            StateSchema: Latest state data with stone coordinate data
        """
        async with session:
            try:
                stmt = (
                    select(State)
                    .options(
                        joinedload(State.stone_coordinate),
                        joinedload(State.score),
                        joinedload(State.shot_info),
                    )
                    .where(State.match_id == match_id)
                    .order_by(desc(State.created_at))
                    .limit(1)
                )
                result = await session.execute(stmt)
                result = result.scalars().first()

                if result is None:
                    return None

                if result.stone_coordinate and isinstance(
                    result.stone_coordinate.stone_coordinate_data, dict
                ):
                    result.stone_coordinate.stone_coordinate_data = json.dumps(
                        result.stone_coordinate.stone_coordinate_data
                    )

                state_data = StateSchema.model_validate(result)
                return state_data

            except Exception as e:
                logging.error(f"Failed to read latest state data: {e}")

    @staticmethod
    async def read_stone_data(stone_coordinate_id: UUID, session: AsyncSession) -> StoneCoordinateSchema:
        """Read stone coordinate data from database

        Args:
            stone_coordinate_id (UUID): To identify the stone coordinate data

        Returns:
            StoneCoordinateSchema: Stone coordinate data
        """
        async with session:
            try:
                stmt = select(StoneCoordinate).where(
                    StoneCoordinate.stone_coordinate_id == stone_coordinate_id
                )
                result = await session.execute(stmt)
                result = result.scalars().first()

                if result is None:
                    return None

                stone_data = StoneCoordinateSchema(
                    stone_coordinate_id=result.stone_coordinate_id,
                    stone_coordinate_data=json.dumps(result.stone_coordinate_data),
                )
                return stone_data

            except Exception as e:
                logging.error(f"Failed to read stone data: {e}")

    @staticmethod
    async def read_score_data(score_id: UUID, session: AsyncSession) -> ScoreSchema:
        """Read score data from database

        Args:
            score_id (UUID): To identify the score data

        Returns:
            ScoreSchema: Score data with first team score and second team score
        """
        async with session:
            try:
                stmt = select(Score).where(Score.score_id == score_id)
                result = await session.execute(stmt)
                result = result.scalars().first()

                if result is None:
                    return None

                score_data = ScoreSchema(
                    score_id=result.score_id,
                    first_team_score=result.first_team_score,
                    second_team_score=result.second_team_score,
                )
                return score_data
            except Exception as e:
                logging.error(f"Failed to read score data: {e}")

    @staticmethod
    async def read_player_data(player_id: UUID, session: AsyncSession) -> PlayerSchema:
        """Read player data from database

        Args:
            player_id (UUID): To identify the player

        Returns:
            PlayerSchema: Player data with player name, team id, max velocity, shot dispersion rate
        """
        async with session:
            try:
                stmt = select(Player).where(Player.player_id == player_id)
                result = await session.execute(stmt)
                result = result.scalars().first()

                if result is None:
                    return None

                player_data = PlayerSchema.model_validate(result)

                return player_data

            except Exception as e:
                logging.error(f"Failed to read player data: {e}")


    @staticmethod
    async def read_simulator_name(match_id, session: AsyncSession) -> str:
        """Read simulator name from match data

        Args:
            match_id (UUID): To identify the match

        Returns:
            str: Simulator name
        """
        async with session:
            try:
                stmt = select(Match.simulator).where(Match.match_id == match_id)
                result = await session.execute(stmt)
                result = result.scalars().first()
                simulator_name = result.simulator.simulator_name
                return simulator_name
            except Exception as e:
                logging.error(f"Failed to read simulator name: {e}")


class CreateData:
    # @staticmethod
    # async def create_table() -> None:
    #     """Create table if not exists"""
    #     try:
    #         async with engine.begin() as conn:
    #             # テーブル作成 (既存テーブルがある場合はスキップされる)
    #             await conn.run_sync(Base.metadata.create_all)
    #     except IntegrityError as e:
    #         logging.warning(f"Table already exists or other integrity error: {e}")

    @staticmethod
    async def create_match_data(match: MatchDataSchema, session: AsyncSession):
        """Create match data with score, tournament, simulator data

        Args:
            match (MatchDataSchema): Match data with score, tournament, simulator data
            session (AsyncSession): AsyncSession object to interact with database
        """
        async with session:
            try:
                new_score = Score(
                    score_id=match.score.score_id,
                    first_team_score=match.score.first_team_score,
                    second_team_score=match.score.second_team_score,
                )
                new_simulator = PhysicalSimulator(
                    physical_simulator_id=match.simulator.physical_simulator_id,
                    simulator_name=match.simulator.simulator_name,
                )
                new_tournament = Tournament(
                    tournament_id=match.tournament.tournament_id,
                    tournament_name=match.tournament.tournament_name,
                )

                new_match = Match(
                    match_id=match.match_id,
                    first_team_name=match.first_team_name,
                    second_team_name=match.second_team_name,
                    first_team_id=match.first_team_id,
                    first_team_player1_id=match.first_team_player1_id,
                    first_team_player2_id=match.first_team_player2_id,
                    first_team_player3_id=match.first_team_player3_id,
                    first_team_player4_id=match.first_team_player4_id,
                    second_team_id=match.second_team_id,
                    second_team_player1_id=match.second_team_player1_id,
                    second_team_player2_id=match.second_team_player2_id,
                    second_team_player3_id=match.second_team_player3_id,
                    second_team_player4_id=match.second_team_player4_id,
                    score_id=match.score_id,
                    time_limit=match.time_limit,
                    extra_end_time_limit=match.extra_end_time_limit,
                    standard_end_count=match.standard_end_count,
                    physical_simulator_id=match.physical_simulator_id,
                    tournament_id=match.tournament_id,
                    match_name=match.match_name,
                    created_at=match.created_at,
                    started_at=match.started_at,
                )
                session.add_all([new_score, new_simulator, new_tournament, new_match])
                await session.commit()

            except Exception as e:
                logging.error(f"Failed to create match data: {e}")

    @staticmethod
    async def create_state_data(state: StateSchema, session: AsyncSession):
        """Create state data with stone coordinate data

        Args:
            state (StateSchema): State data with stone coordinate data
        """
        async with session:
            try:
                new_stone_coordinate = StoneCoordinate(
                    stone_coordinate_id=state.stone_coordinate.stone_coordinate_id,
                    stone_coordinate_data=state.stone_coordinate.stone_coordinate_data,
                )

                new_state = State(
                    state_id=state.state_id,
                    winner_team=state.winner_team,
                    match_id=state.match_id,
                    end_number=state.end_number,
                    shot_number=state.shot_number,
                    total_shot_number=state.total_shot_number,
                    first_team_remaining_time=state.first_team_remaining_time,
                    second_team_remaining_time=state.second_team_remaining_time,
                    first_team_extra_end_remaining_time=state.first_team_extra_end_remaining_time,
                    second_team_extra_end_remaining_time=state.second_team_extra_end_remaining_time,
                    stone_coordinate_id=state.stone_coordinate_id,
                    score_id=state.score_id,
                    shot_id=state.shot_id,
                    next_shot_team=state.next_shot_team,
                    created_at=state.created_at,
                )
                session.add_all([new_stone_coordinate, new_state])
                await session.commit()
            except Exception as e:
                logging.error(f"Failed to create state data: {e}")

    @staticmethod
    async def create_stone_data(stone: StoneCoordinateSchema, session: AsyncSession):
        """Create stone coordinate data

        Args:
            stone (StoneCoordinateSchema): Stone coordinate data
        """
        async with session:
            try:
                new_stone = StoneCoordinate(
                    stone_coordinate_id=stone.stone_coordinate_id,
                    stone_coordinate_data=stone.stone_coordinate_data,
                )
                session.add(new_stone)
                await session.commit()
            except Exception as e:
                logging.error(f"Failed to create stone data: {e}")

    @staticmethod
    async def create_score_data(score: ScoreSchema, session: AsyncSession):
        """Create score data

        Args:
            score (ScoreSchema): Score data with first team score and second team score
        """
        async with session:
            try:
                new_score = Score(
                    score_id=score.score_id,
                    first_team_score=score.first_team_score,
                    second_team_score=score.second_team_score,
                )
                session.add(new_score)
                await session.commit()
            except Exception as e:
                logging.error(f"Failed to create score data: {e}")

    @staticmethod
    async def create_shot_info_data(shot_info: ShotInfoSchema, session: AsyncSession):
        """Create shot info data which is changed by dispersion rate

        Args:
            shot_info (ShotInfoSchema): _description_
        """
        async with session:
            try:
                new_shot_info = ShotInfo(
                    shot_id=shot_info.shot_id,
                    player_id=shot_info.player_id,
                    team_id=shot_info.team_id,
                    trajectory_id=shot_info.trajectory_id,
                    pre_shot_state_id=shot_info.pre_shot_state_id,
                    post_shot_state_id=shot_info.post_shot_state_id,
                    velocity_x=shot_info.velocity_x,
                    velocity_y=shot_info.velocity_y,
                    angular_velocity_sign=shot_info.angular_velocity_sign,
                )
                session.add(new_shot_info)
                await session.commit()
            except Exception as e:
                logging.error(f"Failed to create shot info data: {e}")

    @staticmethod
    async def create_tournament_data(tournament: TournamentSchema, session: AsyncSession):
        """Create tournament data

        Args:
            tournament (TournamentSchema): Tournament data with tournament name
        """
        async with session:
            try:
                new_tournament = Tournament(
                    tournament_id=tournament.tournament_id,
                    tournament_name=tournament.tournament_name,
                )
                session.add(new_tournament)
                await session.commit()
            except Exception as e:
                logging.error(f"Failed to create tournament data: {e}")

    @staticmethod
    async def create_physical_simulator_data(simulator: PhysicalSimulatorSchema, session: AsyncSession):
        """Create physical simulator data

        Args:
            simulator (PhysicalSimulatorSchema): Physical simulator data with simulator name
        """
        async with session:
            try:
                new_simulator = PhysicalSimulator(
                    physical_simulator_id=simulator.physical_simulator_id,
                    simulator_name=simulator.simulator_name,
                )
                session.add(new_simulator)
                await session.commit()
            except Exception as e:
                logging.error(f"Failed to create physical simulator data: {e}")

    @staticmethod
    async def create_team_data(team: TeamSchema, session: AsyncSession):
        """Create team data with 4 players data

        Args:
            team (TeamSchema): Team data with 4 players data
        """
        async with session:
            try:
                new_player1_data = Player(
                    player_id=team.player1.player_id,
                    team_id=team.player1.team_id,
                    max_velocity=team.player1.max_velocity,
                    shot_dispersion_rate=team.player1.shot_dispersion_rate,
                    player_name=team.player1.player_name,
                )
                session.add(new_player1_data)
                new_player2_data = Player(
                    player_id=team.player2.player_id,
                    team_id=team.player2.team_id,
                    max_velocity=team.player2.max_velocity,
                    shot_dispersion_rate=team.player2.shot_dispersion_rate,
                    player_name=team.player2.player_name,
                )
                session.add(new_player2_data)
                new_player3_data = Player(
                    player_id=team.player3.player_id,
                    team_id=team.player3.team_id,
                    max_velocity=team.player3.max_velocity,
                    shot_dispersion_rate=team.player3.shot_dispersion_rate,
                    player_name=team.player3.player_name,
                )
                session.add(new_player3_data)
                new_player4_data = Player(
                    player_id=team.player4.player_id,
                    team_id=team.player4.team_id,
                    max_velocity=team.player4.max_velocity,
                    shot_dispersion_rate=team.player4.shot_dispersion_rate,
                    player_name=team.player4.player_name,
                )
                session.add(new_player4_data)
                await session.commit()

            except Exception as e:
                logging.error(f"Failed to create team data: {e}")

    @staticmethod
    async def create_default_player_data(player: PlayerSchema, session: AsyncSession):
        """Create default player data to use learning AI

        Args:
            player (PlayerSchema): Player data with player name, team id, max velocity, shot dispersion rate
        """
        async with session:
            try:
                result = await session.execute(
                    select(Player).where(Player.player_id == player.player_id)
                )
                player_data = result.scalars().first()
                if not player_data:
                    new_player = Player(
                        player_id=player.player_id,
                        team_id=player.team_id,
                        max_velocity=player.max_velocity,
                        shot_dispersion_rate=player.shot_dispersion_rate,
                        player_name=player.player_name,
                    )
                    session.add(new_player)
                    await session.commit()
            except Exception as e:
                logging.error(f"Failed to create default player data: {e}")


class CollectID:
    @staticmethod
    async def collect_state_ids(session: AsyncSession) -> List[UUID]:
        """Collect all state ids from state table

        Returns:
            List[UUID]: List of state ids
        """
        async with session:
            try:
                stmt = select(State.state_id)
                result = await session.execute(stmt)
                state_ids = result.scalars().all()
                return state_ids

            except Exception as e:
                logging.error(f"Failed to collect state ids: {e}")
