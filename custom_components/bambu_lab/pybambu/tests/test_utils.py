from unittest.mock import MagicMock
import json
import os
import asyncio
from typing import Dict, Any, Callable, Optional

from ..const import (
    LOGGER,
)
from ..utils import safe_json_loads

class MqttMessageInfo:
    """Mock MQTT message info object."""
    def __init__(self, mid: int = 1):
        self.mid = mid
        self.rc = 0
        self.is_published = True

class MockMQTTClient:
    """A mock MQTT client for testing printer communications."""
    _connected: bool = False
    
    def __init__(self, mock: str):
        LOGGER.debug(f"********************** RUNNING IN MOCK MODE '{mock}'")
        self.connected = False
        self.subscribed_topics: Dict[str, Callable] = {}
        self.published_messages: Dict[str, list] = {}
        self._on_connect = None
        self._on_message = None
        self._on_disconnect = None
        self._username = None
        self._password = None
        self._mid = 1
        self._test_payload = {}
        self._mock = mock
        self.load_mock_payload(mock)
    
    def load_mock_payload(self, mock: str):
        """Load test payload asynchronously."""
        file_path = os.path.join(os.path.dirname(__file__), f"{mock}.json")
        LOGGER.debug(f"Loading test payload from {mock}.json")
        with open(file_path, 'rb') as f:
            raw_bytes = f.read()
            self._test_payload = safe_json_loads(raw_bytes)
                
    def connect(self, host: str, port: int = 1883, keepalive: int = 60) -> None:
        """Simulate connecting to an MQTT broker."""
        self._connected = True
        if self._on_connect:
            self._on_connect(None, None, 0, None)
            
    def disconnect(self) -> None:
        """Simulate disconnecting from an MQTT broker."""
        self._connected = False
        if self._on_disconnect:
            self._on_disconnect(None, None, 0)
            
    def subscribe(self, topic: str, callback: Optional[Callable] = None) -> None:
        """Subscribe to a topic and store the callback."""
        self.subscribed_topics[topic] = callback
        
    def publish(self, topic: str, payload: str) -> MqttMessageInfo:
        """Publish a message to a topic and store it for verification."""
        LOGGER.debug(f"MQTTMOCK: Publishing message to topic: {topic} '{payload}")

        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            pass

        # Look for command in the payload, handling nested structures
        command = None
        if isinstance(payload, dict):
            # Check for command in info node
            if 'info' in payload and isinstance(payload['info'], dict):
                command = payload['info'].get('command')
            # Check for command in pushing node
            elif 'pushing' in payload and isinstance(payload['pushing'], dict):
                command = payload['pushing'].get('command')
            # Check for command at root level
            else:
                command = payload.get('command')
        
        # If we found a command and have test data for it, simulate a response
        LOGGER.debug(f"MQTTMOCK: Request for command: {command}")
        if command:
            response = self._test_payload.get(command)
            if response is not None and self._on_message:
                LOGGER.debug(f"MQTTMOCK: Found response.")
                message = MagicMock()
                message.topic = topic
                message.payload = json.dumps(response).encode()
                self._on_message(None, None, message)

        message_info = MqttMessageInfo(self._mid)
        self._mid += 1
        return message_info

    @property
    def on_connect(self):
        return self._on_connect

    @on_connect.setter
    def on_connect(self, callback: Callable):
        """Set the on_connect callback."""
        self._on_connect = callback
        
    @property
    def on_message(self):
        return self._on_message
    
    @on_message.setter
    def on_message(self, callback: Callable):
        """Set the on_message callback."""
        self._on_message = callback
        
    @property
    def on_disconnect(self, callback: Callable):
        return self._on_disconnect
    
    @on_disconnect.setter
    def on_disconnect(self, callback: Callable):
        """Set the on_disconnect callback."""
        self._on_disconnect = callback
        
    def simulate_message(self, topic: str, payload: Dict[str, Any]) -> None:
        """Simulate receiving a message on a topic."""
        if topic in self.subscribed_topics:
            callback = self.subscribed_topics[topic]
            if callback:
                # Convert payload to JSON string to simulate MQTT message format
                message = MagicMock()
                message.topic = topic
                message.payload = json.dumps(payload).encode()
                callback(None, None, message)
                
    def get_published_messages(self, topic: str) -> list:
        """Get all messages published to a specific topic."""
        return self.published_messages.get(topic, [])
        
    def clear_published_messages(self) -> None:
        """Clear all published messages."""
        self.published_messages.clear()

    # TLS-related methods
    def tls_set_context(self, context) -> None:
        """Mock setting TLS context."""
        pass

    def tls_set(self, ca_certs=None, certfile=None, keyfile=None, cert_reqs=None, 
                tls_version=None, ciphers=None) -> None:
        """Mock setting TLS parameters."""
        pass

    def tls_insecure_set(self, value: bool) -> None:
        """Mock setting TLS insecure mode."""
        pass

    def username_pw_set(self, username: str, password: str = None) -> None:
        """Mock setting username and password for authentication."""
        self._username = username
        self._password = password

    def loop_start(self) -> None:
        """Mock starting the network loop in a background thread."""
        LOGGER.debug(f"MQTTMOCK: Starting network loop")
        pass

    def loop_stop(self) -> None:
        """Mock stopping the network loop."""
        LOGGER.debug(f"MQTTMOCK: Stopping network loop")
        pass

    def loop_forever(self) -> None:
        """Mock running the network loop forever."""
        LOGGER.debug(f"MQTTMOCK: Running network loop forever - NOT IMPLEMENTED")
        pass

    def reconnect_delay_set(self, min_delay: int = 1, max_delay: int = 120) -> None:
        """Mock setting reconnect delay parameters."""
        pass 