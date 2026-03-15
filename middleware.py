import paho.mqtt.client as mqtt
import mysql.connector
import json
from datetime import datetime

# --- CONFIGURATION ---
DB_CONFIG = {
    'host': 'localhost',
    'user': 'admin_projet',
    'password': 'bts2026',
    'database': 'domotique_db'
}

# --- LOGIQUE BASE DE DONNÉES ---
def insert_measure(sensor_name, value, unit):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        sql_sensor = "INSERT IGNORE INTO capteurs (nom_piece, type_donnee, reference_zigbee) VALUES (%s, %s, %s)"
        cursor.execute(sql_sensor, ('A definir', 'A definir', sensor_name))
        conn.commit()

        cursor.execute("SELECT id_capteur FROM capteurs WHERE reference_zigbee = %s", (sensor_name,))
        result = cursor.fetchone()
        
        if result:
            id_db = int(result[0])  # ✅ FIX #1
            
            sql_measure = "INSERT INTO mesures (id_capteur, valeur, unite, horodatage) VALUES (%s, %s, %s, %s)"
            cursor.execute(sql_measure, (id_db, float(value), unit, datetime.now()))
            conn.commit()
            print(f"Succes : {value}{unit} enregistre pour '{sensor_name}' (ID: {id_db})")
            
        cursor.close()
        conn.close()

    except Exception as e:
        print(f"Erreur technique MySQL : {e}")  # ✅ Plus de pass silencieux

# --- LOGIQUE MQTT ---
def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        sensor_name = msg.topic.replace('zigbee2mqtt/', '', 1)  # ✅ FIX #3

        # On ignore les topics systèmes de Zigbee2MQTT
        if 'bridge' in sensor_name:
            return

        if 'occupancy' in payload:
            val = 1 if payload['occupancy'] else 0
            insert_measure(sensor_name, val, 'mouv')

        if 'temperature' in payload:
            insert_measure(sensor_name, payload['temperature'], '°C')

        if 'humidity' in payload:
            insert_measure(sensor_name, payload['humidity'], '%')

    except Exception as e:
        print(f"Erreur traitement message MQTT : {e}")  # ✅ Erreurs visibles

# --- DÉMARRAGE DU SERVICE ---
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
client.on_message = on_message
client.connect("localhost", 1883, 60)
client.subscribe("zigbee2mqtt/#")  # ✅ FIX #2
print("Middleware operationnel. En attente de donnees des capteurs...")
client.loop_forever()
