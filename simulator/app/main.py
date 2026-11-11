"""Simulator: refresh active meters, publish monotone cumulative MQTT QoS1."""
from __future__ import annotations
import argparse
import logging
import time
import httpx
from datetime import datetime, timezone
from app.config import Settings
from app.meter_client import MeterClient
from app.mqtt_client import MqttPublisher
from app.virtual_clock import VirtualClock, canonical_time

logger = logging.getLogger('rental.simulator')

def emit_once(settings: Settings, client: MeterClient, publisher: MqttPublisher,
              instant: datetime | None = None, meters=None) -> int:
    if meters is None:
        meters = client.list_active()
    timestamp = canonical_time(instant or datetime.now(timezone.utc))
    clock = VirtualClock(settings)
    
    for meter in meters:
        baseline = client.get_baseline(meter.id)

        value = clock.reading(
            meter.id,
            meter.meter_type,
            timestamp,
            base_reading=baseline.reading_value,
            base_time=baseline.measured_at,
        )

        publisher.publish(
            meter.id,
            timestamp.isoformat(),
            str(value),
        )

    return len(meters)


def run(settings: Settings, *, once=False):
    client = MeterClient(settings)
    with MqttPublisher(settings) as publisher:
        if once:
            count = emit_once(settings, client, publisher)
            logger.info('Published %s cumulative meter readings (QoS1)', count)
            return
        # Failed HTTP listing or MQTT delivery never silently invents meters.
        # Re-fetch each cycle; list-active may change after RoomCreated.
        cached = None
        refreshed_at = 0.0
        while True:
            try:
                if cached is None or time.monotonic() - refreshed_at >= settings.refresh_seconds:
                    cached = client.list_active()
                    refreshed_at = time.monotonic()
                count = emit_once(settings, client, publisher, meters=cached)
                logger.info('Published %s cumulative meter readings (QoS1)', count)
            except (httpx.HTTPError, OSError, ValueError, ConnectionError, TimeoutError) as exc:
                # Never keep publishing indefinitely from a stale meter list.
                cached = None
                logger.warning('Simulator cycle failed: %s', type(exc).__name__)
            time.sleep(settings.publish_interval_seconds)

def main():
    parser = argparse.ArgumentParser(description='Cumulative MQTT meter simulator')
    parser.add_argument('--once', action='store_true', help='Publish one snapshot and exit')
    args = parser.parse_args()
    logging.basicConfig(level='INFO', format='%(asctime)s %(levelname)s %(message)s')
    run(Settings.from_env(), once=args.once)

if __name__ == '__main__':
    main()
