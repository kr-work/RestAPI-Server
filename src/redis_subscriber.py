import asyncio
import json
import logging
from typing import List, AsyncGenerator
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.crud import ReadData, UpdateData
from src.models.schema_models import StateSchema, MatchDataSchema
from src.models.dc_models import StateModel
from src.converter import DataConverter

HEART_BEAT = 15

logging.basicConfig(level=logging.INFO)

read_data = ReadData()
update_data = UpdateData()
data_converter = DataConverter()


class RedisSubscriber:
    """Redis subscriber class to handle SSE events."""

    def __init__(
        self, Session: async_sessionmaker, match_id: str, match_team_name: str
    ):
        """Initialize RedisSubscriber with session, match_id and match_team_name."""
        self.match_id: str = match_id
        self.Session: async_sessionmaker = Session
        self.match_team_name: str = match_team_name

    async def event_generator(self, channel: str, redis: Redis) -> AsyncGenerator[str, None]:
        """Event generator to handle SSE events.

        Args:
            channel (str): To receive messages from Redis, the channel name is match_id.
            redis (Redis): Redis connection object.
        """
        pubsub = redis.pubsub()
        opponent_connected = False
        match_data: MatchDataSchema = None
        state_data_in_end: List[StateSchema] = []

        while not opponent_connected:
            async with self.Session() as session:
                match_data = await read_data.read_match_data(self.match_id, session)
                if (
                    match_data.first_team_name is not None
                    and match_data.second_team_name is not None
                ):
                    opponent_connected = True
                else:
                    opponent_connected = False
                    await asyncio.sleep(5)

        async with self.Session() as session:
            latest_state_data: StateSchema = await read_data.read_latest_state_data(
                self.match_id, session
            )
            if (
                latest_state_data.end_number == 0
                and latest_state_data.total_shot_number == 0
                and self.match_team_name == "team0"
            ):
                await update_data.update_created_at_state_data(
                    latest_state_data.state_id, session
                )
            state_data_in_end = await read_data.read_state_data_in_end(
                self.match_id, latest_state_data.end_number, session
            )
        for i in range(len(state_data_in_end)):
            state_data: StateModel = data_converter.convert_stateschema_to_statemodel(
                match_data, state_data_in_end[i]
            )
            payload = json.dumps(state_data.model_dump())
            logging.debug(f"Payload: {payload}")
            if i == len(state_data_in_end) - 1:
                sse_message = f"event: latest_state_update\ndata: {payload}\n\n"
                yield sse_message
            else:
                sse_message = f"event: state_update\ndata: {payload}\n\n"
                yield sse_message

        await pubsub.subscribe(channel)
        try:
            while True:
                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=None
                )
                if msg and msg["type"] == "message":
                    async with self.Session() as session:
                        latest_state_data: StateSchema = (
                            await read_data.read_latest_state_data(
                                self.match_id, session
                            )
                        )
                    latest_state_data: StateModel = (
                        data_converter.convert_stateschema_to_statemodel(
                            match_data, latest_state_data
                        )
                    )

                    payload = json.dumps(latest_state_data.model_dump())

                    sse_message = f"event: latest_state_update\ndata: {payload}\n\n"
                    yield sse_message

        finally:
            logging.info("Unsubscribing from channel")
            if pubsub:
                await pubsub.unsubscribe(channel)
                await pubsub.close()
