from collections import defaultdict
import json
from typing import Dict, Set

from fastapi import WebSocket, WebSocketException

from app.core.config import websocket_logger


class ConnectionManager:

    def __init__(self):
        self.connections: Dict[str, Set[WebSocket]] = defaultdict(set)

    def connect(self, room: str, connection: WebSocket):
        """
        Establishes a WebSocket connection for a given room.

        If the room does not already exist in the connections dictionary, it initializes a new set for that ID.
        Adds the provided WebSocket connection to the set associated with the room and accepts the connection.

        Args:
            room (str): The unique identifier for the client.
            connection (WebSocket): The WebSocket connection instance to be managed.

        Returns:
            None

        Raises:
            Any exceptions raised by `connection.accept()` will propagate.
        """
        if room not in self.connections:
            self.connections[room] = set()
        self.connections[room].add(connection)

    def disconnect(self, room: str, connection: WebSocket):
        """
        Disconnects a WebSocket connection for a given room.
        Removes the specified WebSocket connection from the set associated with the room.

        Args:
            room (str): The unique identifier for the client whose connection is to be removed.
            connection (WebSocket): The WebSocket connection instance to be removed.
        """
        if room in self.connections:
            self.connections[room].discard(connection)
            if not self.connections[room]:
                del self.connections[room]

    async def broadcast(self, room: str, message: Dict[str, str]):
        """
        Broadcasts a message to all active WebSocket connections in a specified room.

        Args:
            room (str): The identifier for the room whose connections will receive the message.
            message (Dict[str, str]): The message to be sent to each connection.

        Raises:
            WebSocketException: If an error occurs while sending the message to a connection.

        Logs:
            Errors encountered during message sending and warnings if the specified room has no active connections.
        """
        if room in self.connections:
            for connection in self.connections[room]:
                try:
                    await connection.send_text(json.dumps(message))
                except WebSocketException as e:
                    websocket_logger.error(f"Error sending message to {room}: {e}")
                    await self.disconnect(room, connection)
        else:
            websocket_logger.warning(
                f"No connections found for ID: {room}\nAvailable IDs: {list(self.connections.keys())}"
            )

    async def send(self, room: str, message: Dict[str, str]):
        """
        Send a message to the first active WebSocket connection in the specified room.

        Args:
            room (str): The identifier for the room whose connection will receive the message.
            message (Dict[str, str]): The message to send, represented as a dictionary.

        Raises:
            Logs an error and disconnects the connection if sending fails.
            Logs an error if no connections are found for the specified room.
        """
        if room in self.connections and self.connections[room]:
            connection = next(iter(self.connections[room]))
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                websocket_logger.error(f"Error sending message: {e}")
                await self.disconnect(room, connection)
        else:
            websocket_logger.error(f"No connections found for ID: {room}")


manager = ConnectionManager()


def get_websocket_manager() -> ConnectionManager:
    """
    Dependency to get the ConnectionManager instance.

    Returns:
        ConnectionManager: An instance of ConnectionManager for managing WebSocket connections.
    """
    return manager
