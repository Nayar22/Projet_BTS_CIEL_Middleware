import paho.mqtt.client as mqtt
import mysql.connector
import json
from datetime import datetime

# ─── CONFIGURATION ───────────────────────────────────────
DB_CONFIG = {
    'host': 'localhost',
    'user': 'admin_projet',
    'password': 'bts2026',
    'database': 'domotique_db'
}

# ─── LOGIQUE BASE DE DONNÉES ───────────────────────────────────────
def insert_measure(sensor_name, value, unit):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        sql_sensor = "INSERT INTO capteurs (nom_piece, type_donnee, reference_zigbee) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE reference_zigbee = reference_zigbee"
        cursor.execute(sql_sensor, ('A definir', 'A definir', sensor_name))
        conn.commit()

        cursor.execute("SELECT id_capteur FROM capteurs WHERE reference_zigbee = %s", (sensor_name,))
        result = cursor.fetchone()
        
        if result:
            id_db = int(result[0])  # Pour avoir un entiet plutot qu'un tuple
            
            sql_measure = "INSERT INTO mesures (id_capteur, valeur, unite, horodatage) VALUES (%s, %s, %s, %s)"
            cursor.execute(sql_measure, (id_db, float(value), unit, datetime.now()))
            conn.commit()
            print(f"Succes : {value} {unit} enregistre pour '{sensor_name}' (ID: {id_db})")
            
        cursor.close()
        conn.close()

    except Exception as e:
        print(f"Erreur technique MySQL : {e}")  # Plus de pass silencieux

# ─── CONFIGURATION AUTOMATISATION ───────────────────────────────────────
import threading

TOPIC_PRISE_EXT_SET = 'zigbee2mqtt/Prise EXT/set'
DUREE_ALLUMAGE = 20  # secondes — timer de sécurité si occupancy:False n'arrive pas

timer_prise_ext = None
prise_ext_allumee = False  # nouveau flag pour éviter les doublons

# ─── CONFIGURATION TÉLÉCOMMANDE ─────────────────────────────────────────
TELECOMMANDE = "Tel gen"  # Nom exact dans Zigbee2MQTT

PRISE_1 = "Prise 1"
PRISE_2 = "Prise 2"
PRISE_3 = "Prise 3"

# Mapping action MQTT → (état, liste de prises)
# O = emergency     → éteint Prise 1, 2, 3
# I = arm_all_zones → allume Prise 1, 2, 3
# A = arm_day_zones → toggle Prise 1
# B = disarm        → toggle Prise 2
ACTIONS_TELECOMMANDE = {
    "emergency":     ("OFF",    [PRISE_1, PRISE_2, PRISE_3]),
    "arm_all_zones": ("ON",     [PRISE_1, PRISE_2, PRISE_3]),
    "arm_day_zones": ("TOGGLE", [PRISE_1]),
    "disarm":        ("TOGGLE", [PRISE_2]),
}

# ─── CONFIGURATION SEUIL TEMPÉRATURE ────────────────────────────────────
SEUIL_TEMP_MIN = 19.0        # °C — en dessous : radiateur ON
PRISE_RADIATEUR = "Prise 1"  # Prise sur laquelle est branché le radiateur
radiateur_allume = False      # Flag pour éviter les doublons de commande


def control_plug(client, plug_name, state):
    """Publie une commande ON / OFF / TOGGLE sur une prise Zigbee"""
    topic = f"zigbee2mqtt/{plug_name}/set"
    payload = json.dumps({"state": state})
    client.publish(topic, payload)
    print(f"  -> Commande {state} envoyee a '{plug_name}'")

def handle_remote(client, action):
    """Gere les boutons de la telecommande"""
    if action not in ACTIONS_TELECOMMANDE:
        print(f"Action telecommande inconnue ignoree : '{action}'")
        return
    state, prises = ACTIONS_TELECOMMANDE[action]
    print(f"Telecommande : action '{action}' -> {state} sur {prises}")
    for prise in prises:
        control_plug(client, prise, state)

# ─── LOGIQUE MQTT ───────────────────────────────────────
def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        sensor_name = msg.topic.replace('zigbee2mqtt/', '', 1)  # donne bien "Cap temp/humi"

        # On ignore les topics systèmes de Zigbee2MQTT
        if 'bridge' in sensor_name:
            return

        # ── Gestion de la télécommande ───────────────────────────────────────
        if sensor_name == TELECOMMANDE:
            action = payload.get('action', '')
            if action:
                handle_remote(client, action)
            return  # On ne stocke pas les actions télécommande en BDD

        if 'occupancy' in payload:
            val = 1 if payload['occupancy'] else 0
            insert_measure(sensor_name, val, 'mouv')

        if 'temperature' in payload:
            insert_measure(sensor_name, payload['temperature'], '°C')
            gerer_seuil_temperature(client, payload['temperature'])   # pour gérer la température

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
               print("Plus de mouvement : Prise EXT eteinte")  
        # -- Luminosité (NOUVEAU) --
        if "illuminance_lux" in payload:
            lux = payload["illuminance_lux"]
            curseur.execute("""
                INSERT INTO mesures (id_capteur, valeur, unite)
                SELECT id_capteur, %s, 'lx'
                FROM capteurs
                WHERE reference_zigbee = 'Dec mouv_lux' AND type_donnee = 'Luminosité'
                LIMIT 1
            """, (lux,))
            connexion.commit()
            print(f"[Dec mouv] Luminosité : {lux} lx")
    except Exception as e:
        print(f"Erreur traitement message MQTT : {e}")  


def allumer_prise_ext(client):
    global timer_prise_ext, prise_ext_allumee

    # Si déjà allumée, on remet juste le timer à zéro sans republier
    if prise_ext_allumee:
        if timer_prise_ext is not None:
            timer_prise_ext.cancel()
        timer_prise_ext = threading.Timer(DUREE_ALLUMAGE, eteindre_prise_ext, args=[client])
        timer_prise_ext.start()
        print(f"Mouvement continu : timer reinitialiser ({DUREE_ALLUMAGE}s)")
        return

    # Première détection : allumer la prise
    client.publish(TOPIC_PRISE_EXT_SET, json.dumps({"state": "ON"}))
    prise_ext_allumee = True
    print("Mouvement detecte : Prise EXT allumer")

    # Timer de sécurité (au cas où occupancy:False n'arrive jamais)
    timer_prise_ext = threading.Timer(DUREE_ALLUMAGE, eteindre_prise_ext, args=[client])
    timer_prise_ext.start()


def eteindre_prise_ext(client):
    global timer_prise_ext, prise_ext_allumee

    client.publish(TOPIC_PRISE_EXT_SET, json.dumps({"state": "OFF"}))
    prise_ext_allumee = False
    timer_prise_ext = None
    print(f"Prise EXT eteinte")

def gerer_seuil_temperature(client, temperature):
    global radiateur_allume

    if temperature < SEUIL_TEMP_MIN and not radiateur_allume:
        client.publish(f"zigbee2mqtt/{PRISE_RADIATEUR}/set", json.dumps({"state": "ON"}))
        radiateur_allume = True
        print(f"Temp {temperature}C < {SEUIL_TEMP_MIN}C : Radiateur ON")

    elif temperature >= SEUIL_TEMP_MIN and radiateur_allume:
        client.publish(f"zigbee2mqtt/{PRISE_RADIATEUR}/set", json.dumps({"state": "OFF"}))
        radiateur_allume = False
        print(f"Temp {temperature}C >= {SEUIL_TEMP_MIN}C : Radiateur OFF")
        
# ── DÉMARRAGE DU SERVICE ───────────────────────────────────────
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
client.on_message = on_message
client.connect("localhost", 1883, 60)
client.subscribe("zigbee2mqtt/#")  # capte TOUS les niveaux
print("Middleware operationnel. En attente de donnees des capteurs...")
client.loop_forever()
