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
        
        # 1. Auto-Découverte : On insère le capteur s'il n'existe pas
        sql_sensor = "INSERT IGNORE INTO capteurs (nom_piece, type_donnee, reference_zigbee) VALUES (%s, %s, %s)"
        cursor.execute(sql_sensor, ('A definir', 'Inconnu', sensor_name))
        conn.commit()

        # 2. Récupération de l'ID (Extraction du tuple forcée)
        cursor.execute("SELECT id_capteur FROM capteurs WHERE reference_zigbee = %s", (sensor_name,))
        row = cursor.fetchone()
        
        if row:
            # ON EXTRAIT LE PREMIER ÉLÉMENT ET ON FORCE LE TYPE ENTIER [4, 5]
            id_db = int(row) 
            
            # 3. Insertion de la mesure (On force le type float pour la valeur)
            sql_measure = "INSERT INTO mesures (id_capteur, valeur, unite, horodatage) VALUES (%s, %s, %s, %s)"
            cursor.execute(sql_measure, (id_db, float(value), unit, datetime.now()))
            
            conn.commit()
            print(f"OK - Enregistre : {value}{unit} pour {sensor_name} (ID: {id_db})")
        else:
            print(f"Erreur : Impossible de trouver l'ID pour {sensor_name}")
            
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Erreur Python/MySQL : {e}")

# --- LOGIQUE MQTT ---
def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        sensor_name = msg.topic.split('/')[-1]

        if sensor_name == "bridge": return

        # Capteur de mouvement (Detec mouv)
        if 'occupancy' in payload:
            val = 1 if payload['occupancy'] else 0
            insert_measure(sensor_name, val, 'mouv')

        # Capteur température/humidité (Cap temp/humi)
        if 'temperature' in payload:
            insert_measure(sensor_name, payload['temperature'], '°C')
            
        if 'humidity' in payload:
            insert_measure(sensor_name, payload['humidity'], '%')

    except Exception as e:
        pass 

# --- DÉMARRAGE ---
# On utilise explicitement la version 1 de l'API pour supprimer le Warning [1]
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
client.on_message = on_message
client.connect("localhost", 1883, 60)
client.subscribe("zigbee2mqtt/+")

print("Middleware professionnel opérationnel. En attente de données...")
client.loop_forever()
