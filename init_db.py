"""
init_db.py — Classroom
=======================
Prépare la base Classroom à la main (tables + éventuel seed de test),
utile avant un premier déploiement ou pour une base neuve en local.

Important : `app.py` appelle déjà `create_tables()` ET `seed_test_data()`
tout seul au chargement du module (nécessaire pour gunicorn sur Render).
Importer `app` ici déclenche donc les deux, dans cet ordre, avant même
la ligne ci-dessous. Ce n'est plus un problème depuis le correctif :
- create_tables() est sans danger, ne dépend d'aucun service externe.
- seed_test_data() ne crée plus de compte Classroom local sans confir-
  mation d'Octix, et un échec (Octix injoignable) se contente d'un
  warning au lieu de faire planter le démarrage.

Ce script n'ajoute donc rien que `app.py` ne fasse déjà tout seul — il
est surtout là pour lancer cette initialisation manuellement, en dehors
de gunicorn, par exemple pour observer les logs en local.

Usage :
    python init_db.py
"""

import app as classroom_app  # déclenche create_tables() + seed_test_data()

print("Base Classroom initialisée (tables créées, seed exécuté si Octix disponible).")
