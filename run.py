#!/usr/bin/env python3
from playwright.sync_api import sync_playwright
from datetime import datetime
import time, json, os, sys, schedule, threading
import paho.mqtt.client as mqtt

# Configuration from environment
MQTT_BROKER       = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT         = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC_PREFIX = os.getenv("MQTT_TOPIC_PREFIX", "bytewatt")
MQTT_CLIENT_ID    = os.getenv("MQTT_CLIENT_ID", "homeassistant")
MQTT_USERNAME     = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD     = os.getenv("MQTT_PASSWORD", "")
SYS_SN            = os.getenv("SYS_SN", "")
STATION_ID        = os.getenv("STATION_ID", "")

# Directory for local JSON dumps
DATA_DIR = "/data/power_data"
os.makedirs(DATA_DIR, exist_ok=True)

# Scheduler for periodic restarts
def restart():
    os.execv(sys.executable, [sys.executable] + sys.argv)

# Restart at 02:00, 04:00, 13:00, and 22:00 each day
for t in ["02:00", "04:00", "13:00", "22:00"]:
    schedule.every().day.at(t).do(restart)

def run_scheduler():
    threading.Thread(
        target=lambda: [schedule.run_pending() or time.sleep(1) for _ in iter(int, 1)],
        daemon=True
    ).start()

# MQTT setup
def on_mqtt_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT Broker!")
    else:
        print(f"Failed to connect, return code {rc}")

def setup_mqtt():
    client = mqtt.Client(MQTT_CLIENT_ID)
    client.on_connect = on_mqtt_connect
    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    try:
        client.connect(MQTT_BROKER, MQTT_PORT)
    except Exception as e:
        print("Error connecting to MQTT broker:", e)
        return None
    client.loop_start()
    publish_discovery_messages(client)
    return client

# Helpers
def save_data_locally(data, basename):
    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"{basename}_{date_str}.json"
    path = os.path.join(DATA_DIR, filename)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

# Page login & API triggers
def login_by_labels(page, url, username, password):
    page.goto(url)
    try:
        page.locator('input[placeholder="Please enter username/email"]').fill(username)
        page.locator('input[placeholder="Please enter the password"]').fill(password)
        page.locator('button:has-text("Log In")').click()
        page.wait_for_selector("text=Dashboard", timeout=15000)
        return True
    except:
        return False

def trigger_api_requests(page):
    energy_url = f"/api/report/energy/getEnergyStatistics?sysSn={SYS_SN}&stationId={STATION_ID}"
    power_url  = f"/api/report/energyStorage/getLastPowerData?sysSn={SYS_SN}&stationId={STATION_ID}"
    stats_url  = f"/api/report/energy/getStaticsByDay?sysSn={SYS_SN}&stationId={STATION_ID}"
    page.evaluate(f"""() => {{
        fetch("{energy_url}");
        fetch("{power_url}");
        fetch("{stats_url}");
    }}""")

latest_statics_by_day = None

def process_energy_statistics(response, mqtt_client):
    global latest_statics_by_day
    data = response.json()
    if data.get('code') == 200 and 'data' in data:
        energy = data['data']
        payload = {
            "timestamp": datetime.now().isoformat(),
            "energy_stats": {
                "solar_today": energy.get("epvT", 0),
                "total_consumption": energy.get("eload", 0),
                "feed_in": energy.get("eout", 0),
                "grid_import": energy.get("einput", 0),
                "battery_charge": energy.get("echarge", 0),
                "battery_discharge": energy.get("edischarge", 0),
                "self_consumption": energy.get("eselfConsumption", 0),
                "self_sufficiency": energy.get("eselfSufficiency", 0)
            }
        }
        mqtt_client.publish(f"{MQTT_TOPIC_PREFIX}/energy_stats", json.dumps(payload), retain=True)

def process_power_data(response, mqtt_client):
    data = response.json()
    if data.get('code') == 200 and 'data' in data:
        pd = data['data']
        payload = {
            "timestamp": datetime.now().isoformat(),
            "power_stats": {
                "pv_production": pd.get("pvPower", 0),
                "load": pd.get("powerLoad", 0),
                "battery": pd.get("batteryPower", 0),
                "grid": pd.get("gridPower", 0)
            }
        }
        mqtt_client.publish(f"{MQTT_TOPIC_PREFIX}/power_data", json.dumps(payload), retain=True)

def process_statics_by_day(response, mqtt_client):
    global latest_statics_by_day
    data = response.json()
    if data.get('code') == 200 and 'data' in data:
        latest_statics_by_day = data['data']

# Home Assistant auto-discovery
def publish_discovery_messages(client):
    base = MQTT_TOPIC_PREFIX + "/"
    disc = "homeassistant/sensor/bytewatt/"
    sensors = [
        {
            "name": "Current Solar Production",
            "unique_id": "bytewatt_current_solar_production",
            "state_topic": f"{base}power_data",
            "value_template": "{{ value_json.power_stats.pv_production }}",
            "unit_of_measurement": "W",
            "device_class": "power",
            "state_class": "measurement"
        },
        {
            "name": "Current Power Load Requirements",
            "unique_id": "bytewatt_current_load",
            "state_topic": f"{base}power_data",
            "value_template": "{{ value_json.power_stats.load }}",
            "unit_of_measurement": "W",
            "device_class": "power",
            "state_class": "measurement"
        },
        {
            "name": "Battery Power",
            "unique_id": "bytewatt_battery_power",
            "state_topic": f"{base}power_data",
            "value_template": "{{ value_json.power_stats.battery }}",
            "unit_of_measurement": "W",
            "device_class": "power",
            "state_class": "measurement"
        },
        {
            "name": "Grid Power",
            "unique_id": "bytewatt_grid_power",
            "state_topic": f"{base}power_data",
            "value_template": "{{ value_json.power_stats.grid }}",
            "unit_of_measurement": "W",
            "device_class": "power",
            "state_class": "measurement"
        },
        {
            "name": "Today’s Solar Energy (kWh)",
            "unique_id": "bytewatt_solar_today",
            "state_topic": f"{base}energy_stats",
            "value_template": "{{ value_json.energy_stats.solar_today / 1000 }}",
            "unit_of_measurement": "kWh",
            "device_class": "energy",
            "state_class": "total_increasing"
        },
        {
            "name": "Today’s Consumption (kWh)",
            "unique_id": "bytewatt_consumption_today",
            "state_topic": f"{base}energy_stats",
            "value_template": "{{ value_json.energy_stats.total_consumption / 1000 }}",
            "unit_of_measurement": "kWh",
            "device_class": "energy",
            "state_class": "total_increasing"
        }
    ]
    for s in sensors:
        topic = f"{disc}{s['unique_id']}/config"
        client.publish(topic, json.dumps({
            "name": s["name"],
            "state_topic": s["state_topic"],
            "unique_id": s["unique_id"],
            "unit_of_measurement": s["unit_of_measurement"],
            "device_class": s["device_class"],
            "state_class": s["state_class"],
            "value_template": s["value_template"],
            "availability_topic": f"{MQTT_TOPIC_PREFIX}/status"
        }), retain=True)
    client.publish(f"{MQTT_TOPIC_PREFIX}/status", "online", retain=True)

def monitor_system_data():
    mqtt_client = setup_mqtt()
    if not mqtt_client:
        print("MQTT initialization failed. Exiting.")
        return
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        if not login_by_labels(page, "https://monitor.byte-watt.com/login", "", ""):
            print("Login failed—check credentials.")
            return
        page.on("response", lambda resp: (
            process_energy_statistics(resp, mqtt_client) if "/getEnergyStatistics" in resp.url else None,
            process_power_data(resp, mqtt_client)      if "/getLastPowerData"     in resp.url else None,
            process_statics_by_day(resp, mqtt_client)  if "/getStaticsByDay"      in resp.url else None
        ))
        try:
            while True:
                now = datetime.now()
                if now.second % 30 == 0:
                    trigger_api_requests(page)
                if now.hour == 23 and now.minute == 56 and now.second < 5 and latest_statics_by_DAY:
                    save_data_locally({"timestamp": now.isoformat(), "statics_by_day": latest_statics_by_DAY}, "statics_by_day")
                if now.minute % 30 == 0 and now.second < 5:
                    page.reload(wait_until="domcontentloaded")
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            browser.close()
            mqtt_client.publish(f"{MQTT_TOPIC_PREFIX}/status", "offline", retain=True)
            mqtt_client.disconnect()

if __name__ == "__main__":
    run_scheduler()
    monitor_system_data()
