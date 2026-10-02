# Classroom
Une application de classe


## Conserver les classes et les élèves inscrits

Sans configuration, les données sont dans un fichier SQLite local. Sur un hébergeur
dont le disque est éphémère (Render, Vercel…), ce fichier est effacé à chaque
redéploiement ou redémarrage : les classes, les inscriptions, les devoirs et les
copies disparaissent. Pour tout conserver, définir **une** de ces variables
d'environnement :

- `DATABASE_URL` : URL d'une base PostgreSQL hébergée (recommandé en production).
- `DATA_DIR` : chemin d'un disque persistant ; la base SQLite et les fichiers rendus
  par les élèves y seront stockés.
