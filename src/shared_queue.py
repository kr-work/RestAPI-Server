import logging
from multiprocessing.managers import BaseManager
from multiprocessing import Manager
import asyncio
from uuid import UUID


manager = Manager()
queue = asyncio.Queue(maxsize=50)


class SharedList:
    def __init__(self):
        # BaseManagerの初期化
        BaseManager.register("list", list)
        self.manager = BaseManager()
        self.manager.start()
        self.shared_list = manager.list()
        self._lock = asyncio.Lock()
        self._condition = asyncio.Condition()

    async def append(self, notify_payload: UUID):
        """Append the notify_payload to the shared_list

        Args:
            notify_payload (UUID): Payload which contains the match_id to be appended
        """
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, self.shared_list.append, manager.list([notify_payload, 0])
        )

    async def get_all_from_queue(self):
        """Get all the items from the queue and append them to the shared_list"""
        while True:
            if queue.empty():
                break
            notify_payload = await queue.get()
            await self.append(notify_payload)

    async def check_id(self, target_match_id: UUID, increment_count=1) -> bool:
        """Check if the target_match_id is in the shared_list and increment the count if it is

        Args:
            target_match_id (UUID): The match_id to be checked
            increment_count (int, optional): 2 is passed if called by get_match_id, 1 if called by dc function. Defaults to 1.

        Returns:
            bool: True if the target_match_id is in the shared_list, False otherwise
        """
        flag = False
        async with self._lock:
            while not flag:
                await self.get_all_from_queue()
                loop = asyncio.get_running_loop()
                flag = await loop.run_in_executor(
                    None, self._increment_item, target_match_id, increment_count
                )

            # async with self._condition:
            #     self._condition.notify_all()
        return flag

    def _increment_item(self, target_match_id: UUID, increment_count: int) -> bool:
        """Increment the count of the target_match_id in the shared_list

        Args:
            target_match_id (UUID): The match_id to be checked
            increment_count (int): 2 is passed if called by get_match_id, 1 if called by dc function

        Returns:
            bool: True if the target_match_id is in the shared_list, False otherwise
        """        
        for i in range(len(self.shared_list)):
            if self.shared_list[i][0] == str(target_match_id):
                self.shared_list[i][1] += increment_count

                if self.shared_list[i][1] >= 2:
                    self.shared_list.pop(i)

                return True
