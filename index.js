const express = require('express');
const mysql = require('mysql2');
const cors = require('cors');
const app = express();
const port = 3000;
// Configuration CORS : Indispensable pour Etudiant 3 (app mobile)
app.use(cors());
app.use(express.json());
// Configuration de la connexion a la base de données
const db = mysql.createConnection({
  host: 'localhost',
  user: 'admin_projet',
  password: 'bts2026',
  database: 'domotique_db'
});
db.connect(err => {
  if (err) {
    console.error('Erreur de connexion a la base MariaDB :', err.message);
  }
  else {
    console.log('API connectee avec succes a MariaDB sur le Pi.');
  }
});

// ── Connexion MQTT pour le contrôle des prises ──────────────────────────
const mqtt = require('mqtt');

const mqttClient = mqtt.connect('mqtt://localhost:1883');
mqttClient.on('connect', () => {
  console.log('API connectee au broker MQTT.');
});

// Fonction utilitaire : envoie une commande ON/OFF/TOGGLE a une prise
function commandePrise(nomPrise, etat, res) {
  const topic = `zigbee2mqtt/${nomPrise}/set`;
  const payload = JSON.stringify({ state: etat });
  mqttClient.publish(topic, payload, (err) => {
    if (err) {
      console.error(`Erreur MQTT : ${err.message}`);
      return res.status(500).json({ error: 'Erreur envoi commande MQTT' });
    }
    console.log(`Commande ${etat} envoyee a '${nomPrise}'`);
    res.json({ success: true, prise: nomPrise, etat: etat });
  });
}

// Controle individuel : POST /api/prises/Prise 1/on  ou  /off  ou  /toggle
app.post('/api/prises/:nom/:etat', (req, res) => {
  const nom = req.params.nom;
  const etat = req.params.etat.toUpperCase();

  if (!['ON', 'OFF', 'TOGGLE'].includes(etat)) {
    return res.status(400).json({ error: 'Etat invalide. Utiliser ON, OFF ou TOGGLE' });
  }
  commandePrise(nom, etat, res);
});

// Controle global : POST /api/prises/all/on  ou  /off
app.post('/api/prises/all/:etat', (req, res) => {
  const etat = req.params.etat.toUpperCase();

  if (!['ON', 'OFF'].includes(etat)) {
    return res.status(400).json({ error: 'Etat invalide. Utiliser ON ou OFF' });
  }

  const prises = ['Prise 1', 'Prise 2', 'Prise 3'];
  prises.forEach(p => {
    mqttClient.publish(`zigbee2mqtt/${p}/set`, JSON.stringify({ state: etat }));
    console.log(`Commande ${etat} envoyee a '${p}'`);
  });

  res.json({ success: true, prises: prises, etat: etat });
});
// ────────────────────────────────────────────────────────────────────────

//Route Principale pour l'etudiant 3 : Récuperer les dernières mesures
app.get('/api/mesures/last', (req,res) => {
  // Requete SQL utilisant 'horodatage'
  const sql =`
    SELECT c.nom_piece, c.type_donnee, m.valeur, m.unite, m.horodatage
    FROM mesures m
    JOIN capteurs c ON m.id_capteur = c.id_capteur
    WHERE m.horodatage = (SELECT MAX(horodatage) FROM mesures WHERE id_capteur = m.id_capteur)
  `;
  db.query(sql, (err, results) => {
    if (err) {
      console.error(Error('Erreur SQL lors de la lecture :', err.message));
      return res.status(500).json({ error: "Erreur serveur" });
    }
    res.json(results);
  });
});

// ── Contrôle de l'ampoule Amp zig ───────────────────────────────────────
const TOPIC_LAMPE = 'zigbee2mqtt/Amp zig/set';

// Routes spécifiques EN PREMIER
// Luminosité : POST /api/lampe/brightness/:valeur  (0 à 254)
app.post('/api/lampe/brightness/:valeur', (req, res) => {
  const valeur = parseInt(req.params.valeur);
  if (isNaN(valeur) || valeur < 0 || valeur > 254) {
    return res.status(400).json({ error: 'Valeur invalide. Entre 0 et 254' });
  }
  mqttClient.publish(TOPIC_LAMPE, JSON.stringify({ brightness: valeur }));
  console.log(`Lampe : luminosite ${valeur}`);
  res.json({ success: true, brightness: valeur });
});

// Couleur : POST /api/lampe/color  avec body JSON { "r": 255, "g": 0, "b": 128 }
app.post('/api/lampe/color', (req, res) => {
  const { r, g, b } = req.body;
  if (r === undefined || g === undefined || b === undefined) {
    return res.status(400).json({ error: 'Body invalide. Fournir r, g, b (0-255)' });
  }
  mqttClient.publish(TOPIC_LAMPE, JSON.stringify({ color: { r, g, b } }));
  console.log(`Lampe : couleur R${r} G${g} B${b}`);
  res.json({ success: true, color: { r, g, b } });
});

// Route générique EN DERNIER
// Allumer / Éteindre : POST /api/lampe/on  ou  /off
app.post('/api/lampe/:etat', (req, res) => {
  const etat = req.params.etat.toUpperCase();
  if (!['ON', 'OFF'].includes(etat)) {
    return res.status(400).json({ error: 'Etat invalide. Utiliser ON ou OFF' });
  }
  mqttClient.publish(TOPIC_LAMPE, JSON.stringify({ state: etat }));
  console.log(`Lampe : ${etat}`);
  res.json({ success: true, etat: etat });
});
// ────────────────────────────────────────────────────────────────────────

//Lancement du serveur
app.listen(port, () => {
  console.log(`API Domotique active sur le port ${port}`);
  console.log('Adresse pour l app mobile : http://192.168.0.56:3000/api/mesures/last');
});
