"""MQTT v5/3.1.1 QoS 1 publisher using paho-mqtt 2.x callbacks."""
from __future__ import annotations
import json
import socket
import threading
from uuid import UUID
from app.config import Settings

class MqttPublisher:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._connected = threading.Event()
        self.client = None

    def __enter__(self):
        import paho.mqtt.client as mqtt
        # Unique per host. Clean session is fine: a failed publish is retried
        # with the SAME deterministic measured_at/value on the next cycle.
        client_id = 'sim-' + socket.gethostname()[:18]
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id,
                             protocol=mqtt.MQTTv311)
        client.username_pw_set(self.settings.mqtt_username, self.settings.mqtt_password)
        def on_connect(client, userdata, flags, reason_code, properties):
            if reason_code == 0:
                self._connected.set()
            else:
                self._connected.clear()
        def on_disconnect(client, userdata, flags, reason_code, properties):
            self._connected.clear()
        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
        self.client = client
        client.connect(self.settings.mqtt_host, self.settings.mqtt_port, keepalive=45)
        client.loop_start()
        if not self._connected.wait(10):
            self.__exit__(None, None, None)
            raise ConnectionError('MQTT broker connection not acknowledged')
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.client is not None:
            try: self.client.disconnect()
            finally: self.client.loop_stop()
            self.client = None
            self._connected.clear()

    def publish(self, meter_id: UUID, measured_at: str, reading_value: str):
        if self.client is None or not self._connected.is_set():
            raise ConnectionError('MQTT client disconnected')
        topic = f'meters/{meter_id}/reading'
        body = json.dumps({'meter_id':str(meter_id), 'measured_at':measured_at,
                           'reading_value':reading_value}, separators=(',', ':'))
        info = self.client.publish(topic, payload=body, qos=1, retain=False)
        if info.rc != 0:
            raise ConnectionError(f'MQTT publish failed (rc={info.rc})')
        info.wait_for_publish(timeout=10)
        if not info.is_published():
            raise TimeoutError('MQTT QoS1 PUBACK not received')
