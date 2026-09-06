"""
init_db.py — Classroom
=======================
Crée manuellement les tables de la base Classroom, avant un premier
déploiement par exemple.

À savoir : `app.py` appelle déjà `init_db()` tout seul au chargement du
module (nécessaire pour que ça marche sous gunicorn sur Render, comme
pour Octix). Importer `app` ici déclenche donc la même fonction, y
compris le seed de test (comptes prof1/eleve1 + appel réseau à Octix +
création de la classe "Groupe Python"). C'est ce seed qui a provoqué
le crash `FlushError: Can't flush None value found in collection
Classroom.students` quand Octix était injoignable : `octix_register()`
ignore son propre résultat et le code suppose ensuite que les comptes
existent bien.

Ce script ne fait donc rien de plus que lancer `app.py` une fois à la
main, hors gunicorn — utile pour préparer la base avant le premier
déploiement, ou pour rejouer le seed en local en observant les logs.
Tant que le bug du seed (voir ci-dessus) n'est pas corrigé dans
`init_db()`, ce script peut échouer exactement de la même façon si
Octix est injoignable au moment de l'exécution.

Usage :
    python init_db.py
"""

import app as classroom_app  # déclenche db.create_all() + le seed existant

print("Base initialisée (tables créées + seed exécuté par app.py).")
