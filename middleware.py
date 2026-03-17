import paho.mqtt.client as mqtt
import mysql.connector
import json
from datetime import datetime
import sys
sys.stdout.reconfigure(encoding='utf-8')  # ✅ Force l'encodage UTF-8

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

# ─── CONFIGURATION AUTOMATISATION ───────────────────────────────────────
import threading

TOPIC_PRISE_EXT_SET = 'zigbee2mqtt/Prise EXT/set'
DUREE_ALLUMAGE = 10  # secondes — timer de sécurité si occupancy:False n'arrive pas

timer_prise_ext = None
prise_ext_allumee = False  # ← nouveau flag pour éviter les doublons

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
        # ── Automatisation mouvement → Prise EXT ────────────────────────────────
        if 'Dec mouv' in sensor_name and 'occupancy' in payload:
            if payload['occupancy'] is True:
                allumer_prise_ext(client)
            elif payload['occupancy'] is False:
                # Éteindre dès que le capteur ne détecte plus rien
               if timer_prise_ext is not None:
                   timer_prise_ext.cancel()
               eteindre_prise_ext(client)
               print("Plus de mouvement → Prise EXT éteinte")     
    except Exception as e:
        print(f"Erreur traitement message MQTT : {e}")  # ✅ Erreurs visibles


def allumer_prise_ext(client):
    global timer_prise_ext, prise_ext_allumee

    # Si déjà allumée, on remet juste le timer à zéro sans republier
    if prise_ext_allumee:
        if timer_prise_ext is not None:
            timer_prise_ext.cancel()
        timer_prise_ext = threading.Timer(DUREE_ALLUMAGE, eteindre_prise_ext, args=[client])
        timer_prise_ext.start()
        print(f"Mouvement continu — timer réinitialisé ({DUREE_ALLUMAGE}s)")
        return

    # Première détection : allumer la prise
    client.publish(TOPIC_PRISE_EXT_SET, json.dumps({"state": "ON"}))
    prise_ext_allumee = True
    print("Mouvement détecté → Prise EXT allumée")

    # Timer de sécurité (au cas où occupancy:False n'arrive jamais)
    timer_prise_ext = threading.Timer(DUREE_ALLUMAGE, eteindre_prise_ext, args=[client])
    timer_prise_ext.start()


def eteindre_prise_ext(client):
    global timer_prise_ext, prise_ext_allumee

    client.publish(TOPIC_PRISE_EXT_SET, json.dumps({"state": "OFF"}))
    prise_ext_allumee = False
    timer_prise_ext = None
    print(f"Prise EXT éteinte")

# --- DÉMARRAGE DU SERVICE ---
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
client.on_message = on_message
client.connect("localhost", 1883, 60)
client.subscribe("zigbee2mqtt/#")  # ✅ FIX #2
print("Middleware operationnel. En attente de donnees des capteurs...")
client.loop_forever()
