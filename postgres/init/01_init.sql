-- Create Match Table
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

-- Create Score Table
CREATE TABLE IF NOT EXISTS score (
    score_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    first_team_score INTEGER[],
    second_team_score INTEGER[]
);

-- Create PhysicalSimulator Table
CREATE TABLE IF NOT EXISTS physical_simulator (
    physical_simulator_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    simulator_name VARCHAR
);

-- Create Tournament Table
CREATE TABLE IF NOT EXISTS tournament (
    tournament_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tournament_name VARCHAR
);

-- Create ShotInfo Table
CREATE TABLE IF NOT EXISTS shot_info (
    shot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    player_id UUID DEFAULT gen_random_uuid(),
    team_id UUID DEFAULT gen_random_uuid(),
    trajectory_id UUID DEFAULT gen_random_uuid(),
    pre_shot_state_id UUID DEFAULT gen_random_uuid(),
    post_shot_state_id UUID DEFAULT gen_random_uuid(),
    translation_velocity FLOAT,
    angular_velocity_sign INTEGER,
    angular_velocity FLOAT,
    shot_angle FLOAT
);

-- Create State Table
CREATE TABLE IF NOT EXISTS state (
    state_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    winner_team UUID,
    match_id UUID DEFAULT gen_random_uuid(),
    end_number INTEGER,
    shot_number INTEGER,
    total_shot_number INTEGER,
    first_team_remaining_time FLOAT,
    second_team_remaining_time FLOAT,
    first_team_extra_end_remaining_time FLOAT,
    second_team_extra_end_remaining_time FLOAT,
    stone_coordinate_id UUID DEFAULT gen_random_uuid(),
    score_id UUID DEFAULT gen_random_uuid(),
    shot_id UUID,
    next_shot_team UUID DEFAULT gen_random_uuid(),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create StoneCoordinate Table
CREATE TABLE IF NOT EXISTS stone_coordinate (
    stone_coordinate_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stone_coordinate_data JSONB
);

-- Create Trajectory Table
CREATE TABLE IF NOT EXISTS trajectory (
    trajectory_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trajectory_data JSONB,
    data_format_version TEXT
);

-- Create Player Table
CREATE TABLE IF NOT EXISTS player (
    player_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID DEFAULT gen_random_uuid(),
    max_velocity FLOAT,
    shot_dispersion_rate FLOAT,
    player_name VARCHAR
);
