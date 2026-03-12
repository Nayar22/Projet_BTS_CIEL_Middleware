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
        
        # 1. Auto-Découverte : On crée le capteur s'il n'existe pas
        sql_sensor = "INSERT IGNORE INTO capteurs (nom_piece, type_donnee, reference_zigbee) VALUES (%s, %s, %s)"
        cursor.execute(sql_sensor, ('A definir', 'A definir', sensor_name))
        conn.commit()

        # 2. On récupère le numéro ID (Le fetchone renvoie un tuple)
        cursor.execute("SELECT id_capteur FROM capteurs WHERE reference_zigbee = %s", (sensor_name,))
        result = cursor.fetchone()
        
        if result:
            # EXTRACTION DU CHIFFRE PUIS CONVERSION [7, 9]
            id_db = int(result)
            
            # 3. Insertion de la mesure avec typage strict (float pour la valeur)
            sql_measure = "INSERT INTO mesures (id_capteur, valeur, unite, horodatage) VALUES (%s, %s, %s, %s)"
            cursor.execute(sql_measure, (id_db, float(value), unit, datetime.now()))
            conn.commit()
            print(f"Succes : {value}{unit} enregistre pour {sensor_name} (ID: {id_db})")
            
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Erreur technique MySQL : {e}")

# --- LOGIQUE MQTT ---
def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        sensor_name = msg.topic.split('/')[-1]

        if sensor_name == "bridge": return

        # On traite les données selon leur type
        if 'occupancy' in payload:
            val = 1 if payload['occupancy'] else 0
            insert_measure(sensor_name, val, 'mouv')

        if 'temperature' in payload:
            insert_measure(sensor_name, payload['temperature'], '°C')
            
        if 'humidity' in payload:
            insert_measure(sensor_name, payload['humidity'], '%')

    except Exception as e:
        pass # On ignore les messages incomplets

# --- DÉMARRAGE DU SERVICE ---
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
client.on_message = on_message
client.connect("localhost", 1883, 60)
client.subscribe("zigbee2mqtt/+")

print("Middleware operationnel. En attente de mouvements ou temperatures...")
client.loop_forever()
