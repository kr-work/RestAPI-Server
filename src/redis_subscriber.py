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
WAIT_POLL_SECONDS = 5

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
        match_data: MatchDataSchema = None
        state_data_in_end: List[StateSchema] = []

        presence_ttl_seconds = HEART_BEAT * 3

        if self.match_team_name == "viewer":
            pass
        else:
            presence_key_self = f"match:{self.match_id}:presence:{self.match_team_name}"
            presence_key_team0 = f"match:{self.match_id}:presence:team0"
            presence_key_team1 = f"match:{self.match_id}:presence:team1"

            # Mark this SSE connection as present (with TTL in case of abrupt disconnect).
            await redis.set(presence_key_self, "1", ex=presence_ttl_seconds)

            # Wait until both teams are configured (store-team-config) AND both SSE streams are connected.
            while True:
                async with self.Session() as session:
                    match_data = await read_data.read_match_data(self.match_id, session)

                both_teams_configured = (
                    match_data is not None
                    and match_data.first_team_name is not None
                    and match_data.second_team_name is not None
                )
                presence_count = await redis.exists(presence_key_team0, presence_key_team1)
                both_streams_connected = presence_count == 2

                if both_teams_configured and both_streams_connected:
                    break

                # Keep our presence alive while waiting.
                await redis.expire(presence_key_self, presence_ttl_seconds)
                await asyncio.sleep(WAIT_POLL_SECONDS)

            async with self.Session() as session:
                latest_state_data: StateSchema = await read_data.read_latest_state_data(
                    self.match_id, session
                )
                if latest_state_data.end_number == 0 and latest_state_data.total_shot_number == 0:
                    # Set the "start time" exactly once when both players are connected and
                    # the initial board is about to be sent. We use Redis SETNX to prevent
                    # double-updates across concurrent/reconnect SSE clients.
                    start_lock_key = f"match:{self.match_id}:initial_state_start_time_set"
                    acquired = await redis.set(start_lock_key, "1", nx=True, ex=60 * 60 * 24)
                    if acquired:
                        await update_data.update_created_at_state_data(
                            latest_state_data.state_id, session
                        )
                state_data_in_end = await read_data.read_state_data_in_end(
                    self.match_id, latest_state_data.end_number, session
                )
            for i in range(len(state_data_in_end)):
                shot_info_data = None
                async with self.Session() as session:
                    shot_info_data = await read_data.read_last_shot_info_by_post_state_id(
                        state_data_in_end[i].state_id, session
                    )
                state_data: StateModel = data_converter.convert_stateschema_to_statemodel(
                    match_data, state_data_in_end[i], shot_info_data
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
                    ignore_subscribe_messages=True, timeout=HEART_BEAT
                )
                # Heartbeat: refresh presence TTL and keep SSE connection alive.
                await redis.expire(presence_key_self, presence_ttl_seconds)

                if msg is None:
                    yield ": ping\n\n"
                    continue
                if msg and msg["type"] == "message":
                    async with self.Session() as session:
                        latest_state_data: StateSchema = (
                            await read_data.read_latest_state_data(
                                self.match_id, session
                            )
                        )
                        shot_info_data = None
                        if latest_state_data is not None:
                            shot_info_data = await read_data.read_last_shot_info_by_post_state_id(
                                latest_state_data.state_id, session
                            )
                    latest_state_data: StateModel = (
                        data_converter.convert_stateschema_to_statemodel(
                            match_data, latest_state_data, shot_info_data
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
            # Remove this connection's presence flag.
            await redis.delete(presence_key_self)
