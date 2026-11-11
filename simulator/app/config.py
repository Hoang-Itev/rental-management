"""P06 simulator settings. Never log MQTT credentials or SERVICE_TOKEN."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import os

@dataclass(frozen=True)
class Settings:
    metering_url: str
    service_token: str
    mqtt_host: str
    mqtt_port: int
    mqtt_username: str
    mqtt_password: str
    publish_interval_seconds: int
    refresh_seconds: int
    time_scale: Decimal
    epoch: datetime
    electricity_kwh_per_day: Decimal
    water_m3_per_day: Decimal

    @classmethod
    def from_env(cls):
        settings = cls(
            metering_url=os.environ.get('METERING_URL','http://metering:8000'),
            service_token=os.environ.get('SERVICE_TOKEN',''),
            mqtt_host=os.environ.get('MQTT_HOST','rabbitmq'),
            mqtt_port=int(os.environ.get('MQTT_PORT','1883')),
            mqtt_username=os.environ.get('MQTT_USERNAME',''),
            mqtt_password=os.environ.get('MQTT_PASSWORD',''),
            publish_interval_seconds=int(os.environ.get('SIM_INTERVAL_SECONDS','300')),
            refresh_seconds=int(os.environ.get('SIM_REFRESH_SECONDS','300')),
            time_scale=Decimal(os.environ.get('SIM_TIME_SCALE','1')),
            epoch=datetime.fromisoformat(os.environ.get('SIM_EPOCH','2026-01-01T00:00:00+00:00').replace('Z','+00:00')),
            electricity_kwh_per_day=Decimal(os.environ.get('SIM_KWH_PER_DAY','4')),
            water_m3_per_day=Decimal(os.environ.get('SIM_M3_PER_DAY','0.5')),
        )
        if len(settings.service_token) < 24:
            raise ValueError('SERVICE_TOKEN must be set (minimum 24 characters)')
        if not settings.mqtt_username or not settings.mqtt_password:
            raise ValueError('MQTT credentials required')
        if not (1 <= settings.mqtt_port <= 65535):
            raise ValueError('Invalid MQTT port')
        if settings.publish_interval_seconds < 1 or settings.refresh_seconds < 1:
            raise ValueError('Simulation intervals must be positive')
        if settings.epoch.tzinfo is None or settings.epoch > datetime.now(timezone.utc):
            raise ValueError('SIM_EPOCH must be a past timezone-aware instant')
        if any(x <= 0 or not x.is_finite() for x in (
            settings.time_scale, settings.electricity_kwh_per_day, settings.water_m3_per_day
        )):
            raise ValueError('Simulation scale and rates must be finite and positive')
        return settings
