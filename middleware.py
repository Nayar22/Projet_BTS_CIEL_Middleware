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
        
        # 1. Tenter d'insérer le capteur s'in n'éxiste pas (Auto-Découverte)
        # On utilise 'INSERT IGNORE' pour ne pas créer de doublon
        sql_sensor = "INSERT IGNORE INTO capteurs (nom_piece, type_donnee, reference_zigbee) VALUES (%s, %s, %s)"
        cursor.execute(sql_sensor, ('A definir', 'Inconnu', sensor_name))
        conn.commit()

        # 2. Récuperer l'ID (qu'il vienne d''être créé ou qu'il existait déja)
        cursor.execute("SELECT id_capteur FROM capteurs WHERE reference_zigbee = %s", (sensor_name,))
        id_db = cursor.fetchone()

        # 3. Insérer la mesure vec le bon numéro d'ID
        sql_mesure = "INSERT INTO mesures (id_capteur, valeur, unite, horodatage) VALUES (%s, %s, %s, %s)"

        cursor.execute(sql_measure, (id_db, value, unit, datetime.now()))

        conn.commit()
        print(f"OK - Enregistre : {value}{unit} pour {sensor_name} (ID: {id_db})")

        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Erreur MySQL : {e}")

# --- LOGIQUE MQTT ---
def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        sensor_name = msg.topic.split('/')[-1]
        print(f"Message recu de : {sensor_name}") # Pour debug

        # Detection de mouvement
        if 'occupancy' in payload:
            val = 1 if payload['occupancy'] else 0
            insert_measure(sensor_name, val, 'mouv')

        # Temperature et Humidite
        if 'temperature' in payload:
            insert_measure(sensor_name, payload['temperature'], '°C')
        if 'humidity' in payload:
            insert_measure(sensor_name, payload['humidity'], '%')

    except Exception as e:
        print(f"Erreur traitement : {e}")

client = mqtt.Client()
client.on_message = on_message
client.connect("localhost", 1883, 60)
client.subscribe("zigbee2mqtt/+")

print("Middleware demarre. En attente de donnees Zigbee...")
client.loop_forever()
