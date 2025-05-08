-- ======================================
-- 1) 拡張を有効化
-- ======================================
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ======================================
-- 2) テーブル本体をすべて作成（FKはあとで）
-- ======================================
-- Score
CREATE TABLE IF NOT EXISTS score (
    score_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team0_score INTEGER[],
    team1_score INTEGER[]
);

-- PhysicalSimulator
CREATE TABLE IF NOT EXISTS physical_simulator (
    physical_simulator_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    simulator_name VARCHAR
);

-- Tournament
CREATE TABLE IF NOT EXISTS tournament (
    tournament_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tournament_name VARCHAR
);

-- StoneCoordinate
CREATE TABLE IF NOT EXISTS stone_coordinate (
    stone_coordinate_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stone_coordinate_data JSONB
);

-- Trajectory
CREATE TABLE IF NOT EXISTS trajectory (
    trajectory_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trajectory_data JSONB,
    data_format_version TEXT
);

-- Player
CREATE TABLE IF NOT EXISTS player (
    player_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID DEFAULT gen_random_uuid(),
    max_velocity DOUBLE PRECISION,
    shot_dispersion_rate DOUBLE PRECISION,
    player_name VARCHAR
);

-- Match
CREATE TABLE IF NOT EXISTS match_data (
    match_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    first_team_name VARCHAR,
    second_team_name VARCHAR,
    first_team_id UUID DEFAULT gen_random_uuid(),
    first_team_player1_id UUID DEFAULT gen_random_uuid(),
    first_team_player2_id UUID DEFAULT gen_random_uuid(),
    first_team_player3_id UUID DEFAULT gen_random_uuid(),
    first_team_player4_id UUID DEFAULT gen_random_uuid(),
    second_team_id UUID DEFAULT gen_random_uuid(),
    second_team_player1_id UUID DEFAULT gen_random_uuid(),
    second_team_player2_id UUID DEFAULT gen_random_uuid(),
    second_team_player3_id UUID DEFAULT gen_random_uuid(),
    second_team_player4_id UUID DEFAULT gen_random_uuid(),
    winner_team_id UUID,
    score_id UUID DEFAULT gen_random_uuid(),
    time_limit INTEGER,
    extra_end_time_limit INTEGER,
    standard_end_count INTEGER,
    physical_simulator_id UUID DEFAULT gen_random_uuid(),
    tournament_id UUID DEFAULT gen_random_uuid(),
    match_name VARCHAR,
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP DEFAULT NOW()
);

-- ShotInfo
CREATE TABLE IF NOT EXISTS shot_info (
    shot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    player_id UUID DEFAULT gen_random_uuid(),
    team_id UUID DEFAULT gen_random_uuid(),
    trajectory_id UUID DEFAULT gen_random_uuid(),
    pre_shot_state_id UUID DEFAULT gen_random_uuid(),
    post_shot_state_id UUID DEFAULT gen_random_uuid(),
    translation_velocity DOUBLE PRECISION,
    angular_velocity_sign INTEGER,
    angular_velocity DOUBLE PRECISION,
    shot_angle DOUBLE PRECISION
);

-- State
CREATE TABLE IF NOT EXISTS state (
    state_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    winner_team_id UUID,
    match_id UUID DEFAULT gen_random_uuid(),
    end_number INTEGER,
    shot_number INTEGER,
    total_shot_number INTEGER,
    first_team_remaining_time DOUBLE PRECISION,
    second_team_remaining_time DOUBLE PRECISION,
    first_team_extra_end_remaining_time DOUBLE PRECISION,
    second_team_extra_end_remaining_time DOUBLE PRECISION,
    stone_coordinate_id UUID DEFAULT gen_random_uuid(),
    score_id UUID DEFAULT gen_random_uuid(),
    shot_id UUID,
    next_shot_team_id UUID DEFAULT gen_random_uuid(),
    created_at TIMESTAMP DEFAULT NOW()
);

-- ======================================
-- 3) 外部キー制約をすべて追加
-- ======================================
-- match_data → score / physical_simulator / tournament / player(x8)
ALTER TABLE match_data
  ADD CONSTRAINT fk_match_score
    FOREIGN KEY(score_id) REFERENCES score(score_id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_match_simulator
    FOREIGN KEY(physical_simulator_id) REFERENCES physical_simulator(physical_simulator_id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_match_tournament
    FOREIGN KEY(tournament_id) REFERENCES tournament(tournament_id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_match_p1  FOREIGN KEY(first_team_player1_id) REFERENCES player(player_id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_match_p2  FOREIGN KEY(first_team_player2_id) REFERENCES player(player_id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_match_p3  FOREIGN KEY(first_team_player3_id) REFERENCES player(player_id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_match_p4  FOREIGN KEY(first_team_player4_id) REFERENCES player(player_id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_match_p5  FOREIGN KEY(second_team_player1_id) REFERENCES player(player_id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_match_p6  FOREIGN KEY(second_team_player2_id) REFERENCES player(player_id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_match_p7  FOREIGN KEY(second_team_player3_id) REFERENCES player(player_id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_match_p8  FOREIGN KEY(second_team_player4_id) REFERENCES player(player_id) ON DELETE CASCADE;

-- shot_info → player / trajectory / state(x2)
ALTER TABLE shot_info
  ADD CONSTRAINT fk_shot_player
    FOREIGN KEY(player_id) REFERENCES player(player_id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_shot_trajectory
    FOREIGN KEY(trajectory_id) REFERENCES trajectory(trajectory_id) ON DELETE CASCADE;

-- state → match_data / score / shot_info / stone_coordinate
ALTER TABLE state
  ADD CONSTRAINT fk_state_match
    FOREIGN KEY(match_id) REFERENCES match_data(match_id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_state_score
    FOREIGN KEY(score_id) REFERENCES score(score_id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_state_stone_coord
    FOREIGN KEY(stone_coordinate_id) REFERENCES stone_coordinate(stone_coordinate_id) ON DELETE CASCADE;
