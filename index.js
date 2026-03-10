const express = require('express');
const mysql = require('cors');
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

//Lancement du serveur
app.listen(port, () => {
  console.log('API Domotique active sur le port ${port}');
  console.log('Adresse pour l'App Mobile : http://192.168.0.56:3000/api/mesures/last');
});
