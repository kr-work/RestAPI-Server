import logging
from asyncio import Condition, Lock
from uuid import UUID


class MatchSyncManager:
    def __init__(self):
        self.conditions = {}  # match_idごとにConditionを管理
        self.ready_counts = {}  # match_idごとの準備完了サーバ数をカウント
        self.lock = Lock()  # ready_countsへのアクセスを保護

    async def get_condition_and_ready_count(self, match_id: UUID) -> Condition:
        """Get the Condition of the specified match_id

        Args:
            match_id (UUID): ID to identify this match

        Returns:
            Condition: Condition of the specified match_id
        """        
        async with self.lock:
            if match_id not in self.conditions:
                self.conditions[match_id] = Condition()
                self.ready_counts[match_id] = 0
            return self.conditions[match_id]
        
    async def increment_ready_count(self, match_id: UUID):
        """Increments the readiness count for the specified match_id

        Args:
            match_id (UUID): ID to identify this match
        """
        async with self.lock:
            self.ready_counts[match_id] += 1
            # logging.info(f"increment_ready_count: {self.ready_counts[match_id]}")

    async def get_ready_count(self, match_id: UUID) -> int:
        """Get the ready count of the specified match_id

        Args:
            match_id (UUID): ID to identify this match

        Returns:
            int: ready count
        """
        async with self.lock:
            return self.ready_counts[match_id]
        
    async def reset_ready_count(self, match_id: UUID):
        """Reset the ready count of the specified match_id

        Args:
            match_id (UUID): ID to identify this match
        """
        async with self.lock:
            if self.ready_counts[match_id] == 2:
                self.ready_counts[match_id] = 0
        
    async def cleanup(self, match_id: UUID):
        """Delete Condition of the specified match_id

        Args:
            match_id (UUID): ID to identify this match
        """        
        async with self.lock:
            if match_id in self.conditions:
                del self.conditions[match_id]
                del self.ready_counts[match_id]