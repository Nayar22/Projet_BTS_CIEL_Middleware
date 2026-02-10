import paho.mqtt.client as mqtt
import mysql.connector
import json
from datetime import datetime

# --- CONFIGURATION ---
# Utilisation des identifiants réels
DB_CONFIG = {
  'host': 'localhost',
  'user': 'admin_projet',
  'password': 'bts2026',
  'database': 'dmotique_db'
}

# --- LOGIQUE BASE DE DONNEES ---
def insert_measure(sensor_id, value, unit):
  try:
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    #Insertopn dans la table 'mesures'
    sql = "INSERT INTO mesures (id_capteur, valeur, unite, date_mesure) VALUES (%s, %s, %s, %s)"
    cursor.execute(sql, (sensor_id, value, unit, datetime.now()))
    conn.commit()
    cursor.close()
    conn.close()
    print (f"✔ Données enregistrée : {value}{unit} pour le capteur {sensor_id}")
  except Exception as e:
    print(f"❌ Erreur MySQL : {e}")

# --- LOGIQUE MQTT  ---
def on_message(client, userdata, msg):
  try:
    # Analyse du message JSON reçu
    payload = json.loads(msg.payload.decode())
    topic = msg.topic.split('/')
    sensor_name = topic[-1]  # Récupere le om du capteur
    
    # Si le capteur Nedis envoie une temperature 
    if 'temperature' in payload:
      temp = payload['temperature']
      insert_mesure(sensor_name, temp, '°C')
    
    # Si le capteur evoie l'humidité
    if 'humidity' in payload:
      hum = payload['humidity']
      insert_measure(sensor_name, temp, '%')
  except Exception as e:
    print(f"⚠ Erreur lors du traitement du message : {e}")

# --- DEMARRAGE DU CLIENT ---
client = mqtt.Client()
client.on_message = on_message

# Connexion au broker local installé avant
client.connect("localhost", 1883, 60)
client.subscribe("zigbee2mqtt/+")  # Ecoute tous les capteurs

print("Middleware démarré. En attente de donées Zigbee. . .")
client.loop_forever()

   
    
