import numpy as np
from typing import List

TEE_LINE = np.float32(38.405)
HOUSE_RADIUS = np.float32(1.829)
STONE_RADIUS = np.float32(0.145)
SCORE_DISTANCE = HOUSE_RADIUS + STONE_RADIUS


class ScoreUtils:
    def get_distance(
        self, team_number: int, x: np.float32, y: np.float32
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

    def get_score(self, distance_list: List[tuple[int, np.float32]]) -> tuple[int, int]:
        """Get how many points either team scored

        Args:
            distance_list (List[tuple[int, np.float32]]): List containing the distance of each stone from the tee

        Returns:
            tuple[int, int]: The team that scored and the number of points scored
        """
        sort_distance_list = sorted(distance_list, key=lambda x: x[1])
        scored_stones = None
        if sort_distance_list[0][1] > SCORE_DISTANCE:
            return None, 0
        scored_stones = sort_distance_list[0][0]
        score = 1

        for team, distance in sort_distance_list[1:]:
            if team == scored_stones and distance <= SCORE_DISTANCE:
                score += 1
            else:
                break
        return scored_stones, score

    def calculate_score(self, score_list: List[int]) -> int:
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
