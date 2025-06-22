#!/usr/bin/env bash
set -e

CONFIG=/data/options.json

# Load options from HA UI
export MQTT_BROKER="$(jq -r '.mqtt_broker' $CONFIG)"
export MQTT_PORT="$(jq -r '.mqtt_port' $CONFIG)"
export MQTT_TOPIC_PREFIX="$(jq -r '.mqtt_topic_prefix' $CONFIG)"
export MQTT_USERNAME="$(jq -r '.mqtt_username' $CONFIG)"
export MQTT_PASSWORD="$(jq -r '.mqtt_password' $CONFIG)"
export SYS_SN="$(jq -r '.system_sn' $CONFIG)"
export STATION_ID="$(jq -r '.station_id' $CONFIG)"

# Ensure data directory exists
mkdir -p /data/power_data

exec python3 /run.py