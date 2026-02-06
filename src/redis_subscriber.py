import asyncio
import json
import logging
from typing import List, AsyncGenerator
from uuid import UUID
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.crud import ReadData, UpdateData
from src.models.schema_models import StateSchema, MatchDataSchema
from src.models.dc_models import StateModel
from src.converter import DataConverter

HEART_BEAT = 30

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
        presence_key_self = None
        presence_ttl_seconds = HEART_BEAT * 3

        await pubsub.subscribe(channel)

        # ---- Initial sync (first board) ----
        if self.match_team_name == "viewer":
            # Viewers do not participate in presence coordination; send the latest state once immediately.
            async with self.Session() as session:
                match_data = await read_data.read_match_data(self.match_id, session)
                latest_state_data: StateSchema | None = await read_data.read_latest_state_data(
                    self.match_id, session
                )
                shot_info_data = None
                md_end_setup = None
                if latest_state_data is not None:
                    shot_info_data = await read_data.read_last_shot_info_by_post_state_id(
                        latest_state_data.state_id, session
                    )
                    if match_data is not None and match_data.game_mode == "mix_doubles":
                        md_end_setup = await read_data.read_mix_doubles_end_setup(
                            self.match_id, latest_state_data.end_number, session
                        )

            latest_state_model: StateModel = data_converter.convert_stateschema_to_statemodel(
                match_data, latest_state_data, shot_info_data, md_end_setup
            )
            payload = json.dumps(latest_state_model.model_dump())
            yield f"event: latest_state_update\ndata: {payload}\n\n"
        else:
            presence_key_self = f"match:{self.match_id}:presence:{self.match_team_name}"
            presence_key_team0 = f"match:{self.match_id}:presence:team0"
            presence_key_team1 = f"match:{self.match_id}:presence:team1"

            config_key_team0 = f"match:{self.match_id}:team_config:team0"
            config_key_team1 = f"match:{self.match_id}:team_config:team1"

            await redis.set(presence_key_self, "1", ex=presence_ttl_seconds)
            await redis.publish(
                channel,
                json.dumps(
                    {
                        "type": "presence_updated",
                        "match_id": str(self.match_id),
                        "team": self.match_team_name,
                    }
                ),
            )

            # If Redis was restarted, team_config keys may be missing even though DB is configured.
            async with self.Session() as session:
                match_data = await read_data.read_match_data(self.match_id, session)
            if (
                match_data is not None
                and match_data.first_team_name is not None
                and match_data.second_team_name is not None
            ):
                await redis.set(config_key_team0, "1", ex=60 * 60 * 24)
                await redis.set(config_key_team1, "1", ex=60 * 60 * 24)

            initial_sync_done = False
            waiting_for_initial_sync_signal = True

            # Event-driven barrier: wait until both streams are connected AND both teams have configured.
            while not initial_sync_done:
                await redis.expire(presence_key_self, presence_ttl_seconds)

                config_count = await redis.exists(config_key_team0, config_key_team1)
                both_teams_configured = config_count == 2

                presence_count = await redis.exists(presence_key_team0, presence_key_team1)
                both_streams_connected = presence_count == 2

                if both_teams_configured and both_streams_connected and waiting_for_initial_sync_signal:
                    # One of the subscribers emits an "initial_sync" signal.
                    signal_lock_key = f"match:{self.match_id}:initial_sync:signal_lock"
                    acquired = await redis.set(signal_lock_key, "1", nx=True, ex=5)
                    if acquired:
                        await redis.publish(
                            channel,
                            json.dumps({"type": "initial_sync", "match_id": str(self.match_id)}),
                        )
                    waiting_for_initial_sync_signal = False

                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=HEART_BEAT
                )
                if msg is None:
                    yield ": ping\n\n"
                    continue

                if msg.get("type") != "message":
                    continue

                msg_type = None
                try:
                    raw = msg.get("data")
                    if isinstance(raw, (bytes, bytearray)):
                        raw = raw.decode("utf-8")
                    if isinstance(raw, str):
                        parsed = json.loads(raw)
                        msg_type = parsed.get("type")
                except Exception:
                    msg_type = None

                if msg_type != "initial_sync":
                    continue

                state_data_in_end: List[StateSchema] = []
                async with self.Session() as session:
                    latest_state_data: StateSchema = await read_data.read_latest_state_data(
                        self.match_id, session
                    )
                    if latest_state_data.end_number == 0 and latest_state_data.total_shot_number in (None, 0):
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
                    async with self.Session() as session:
                        match_data = await read_data.read_match_data(self.match_id, session)
                        shot_info_data = await read_data.read_last_shot_info_by_post_state_id(
                            state_data_in_end[i].state_id, session
                        )
                        md_end_setup = None
                        if match_data is not None and match_data.game_mode == "mix_doubles":
                            md_end_setup = await read_data.read_mix_doubles_end_setup(
                                self.match_id, state_data_in_end[i].end_number, session
                            )
                    state_data: StateModel = data_converter.convert_stateschema_to_statemodel(
                        match_data, state_data_in_end[i], shot_info_data, md_end_setup
                    )
                    payload = json.dumps(state_data.model_dump())
                    logging.debug(f"Payload: {payload}")
                    if i == len(state_data_in_end) - 1:
                        yield f"event: latest_state_update\ndata: {payload}\n\n"
                    else:
                        yield f"event: state_update\ndata: {payload}\n\n"

                initial_sync_done = True
        try:
            while True:
                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=HEART_BEAT
                )
                # Heartbeat: refresh presence TTL and keep SSE connection alive.
                if presence_key_self is not None:
                    await redis.expire(presence_key_self, presence_ttl_seconds)

                if msg is None:
                    yield ": ping\n\n"
                    continue
                if msg and msg["type"] == "message":
                    published_state_id: UUID | None = None
                    msg_type = None
                    try:
                        raw = msg.get("data")
                        if isinstance(raw, (bytes, bytearray)):
                            raw = raw.decode("utf-8")
                        if isinstance(raw, str):
                            parsed = json.loads(raw)
                            msg_type = parsed.get("type")
                            state_id_str = parsed.get("state_id")
                            if state_id_str:
                                published_state_id = UUID(str(state_id_str))
                    except Exception:
                        published_state_id = None

                    # Coordination/control messages are ignored during normal streaming.
                    if msg_type in {"presence_updated", "team_config_updated", "initial_sync"}:
                        continue

                    async with self.Session() as session:
                        match_data = await read_data.read_match_data(self.match_id, session)
                        latest_state_data: StateSchema | None = None
                        if published_state_id is not None:
                            latest_state_data = await read_data.read_state_data(published_state_id, session)
                        if latest_state_data is None:
                            latest_state_data = await read_data.read_latest_state_data(self.match_id, session)
                        shot_info_data = None
                        md_end_setup = None
                        if latest_state_data is not None:
                            shot_info_data = await read_data.read_last_shot_info_by_post_state_id(
                                latest_state_data.state_id, session
                            )
                            if match_data is not None and match_data.game_mode == "mix_doubles":
                                md_end_setup = await read_data.read_mix_doubles_end_setup(
                                    self.match_id, latest_state_data.end_number, session
                                )
                    latest_state_data: StateModel = (
                        data_converter.convert_stateschema_to_statemodel(
                            match_data, latest_state_data, shot_info_data, md_end_setup
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
            if presence_key_self is not None:
                await redis.delete(presence_key_self)
