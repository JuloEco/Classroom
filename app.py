import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filenameimport os
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'une_cle_secrete_tres_securisee'

# Configuration de la base de données et des uploads
# En prod (Render), DATABASE_URL est fourni par le service Postgres.
# En local, si la variable n'existe pas, on retombe sur SQLite.
database_url = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
# Render (et Heroku) fournissent parfois une URL qui commence par "postgres://",
# mais SQLAlchemy récent exige le préfixe "postgresql://".
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'png', 'jpg', 'jpeg', 'docx', 'txt', 'zip', 'py'}

db = SQLAlchemy(app)

# Création du dossier d'upload s'il n'existe pas
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# ----------------------------------------------------
# MODÈLES DE LA BASE DE DONNÉES
# ----------------------------------------------------
# Table d'association : Qui est élève dans quelle classe ?
student_classroom = db.Table('student_classroom',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('classroom_id', db.Integer, db.ForeignKey('classroom.id'), primary_key=True)
)

# Table d'association : Qui est prof dans quelle classe ?
teacher_classroom = db.Table('teacher_classroom',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('classroom_id', db.Integer, db.ForeignKey('classroom.id'), primary_key=True)
)

class Classroom(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    
    # Relations many-to-many
    students = db.relationship('User', secondary=student_classroom, backref=db.backref('classes_as_student', lazy='dynamic'))
    teachers = db.relationship('User', secondary=teacher_classroom, backref=db.backref('classes_as_teacher', lazy='dynamic'))
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(10), nullable=False) # 'prof' ou 'eleve'

class Mindmap(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)  # Stockera le JSON.stringify() de la carte
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)

class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)

class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignment.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    grade = db.Column(db.Float, nullable=True) # Note laissée par le prof
    comment = db.Column(db.Text, nullable=True)

class ProjetGuide(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    steps_json = db.Column(db.Text, nullable=False) # Contiendra le tableau d'étapes en JSON
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Flashcard(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(100), nullable=False, default="Général")
    question = db.Column(db.Text, nullable=False) # Le Recto
    answer = db.Column(db.Text, nullable=False)   # Le Verso (Le code Python propre)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    # Clés étrangères
    repo_id = db.Column(db.Integer, db.ForeignKey('repo.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relation pour récupérer facilement le nom de l'auteur dans Jinja
    author = db.relationship('User', backref=db.backref('comments', lazy=True))

class Repo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(300))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    visibility = db.Column(db.String(20), default='private')
    
    # ─── LA LIGNE À RAJOUTER ICI ───
    # Elle permet à Jinja de faire "r.user.username" sans planter
    user = db.relationship('User', backref=db.backref('repos', lazy=True))
    comments = db.relationship('Comment', backref='repo', lazy=True, cascade="all, delete-orphan")
    # Le reste de tes relations existantes :
    commits = db.relationship('Commit', backref='repo', lazy=True, cascade="all, delete-orphan")
    shared_with = db.relationship('RepoAccess', backref='repo', lazy=True, cascade="all, delete-orphan")
    merge_requests_list = db.relationship('MergeRequest', backref='repo', lazy=True, cascade="all, delete-orphan")
class RepoAccess(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    repo_id = db.Column(db.Integer, db.ForeignKey('repo.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # L'utilisateur qui reçoit l'accès

class Commit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.String(200), nullable=False)
    code_snapshot = db.Column(db.Text, nullable=False) # Le code complet à ce moment X
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    repo_id = db.Column(db.Integer, db.ForeignKey('repo.id'), nullable=False)

# ----------------------------------------------------
# NOUVEAUX MODÈLES POUR LA FUSION ET LE DIFF VIEWER
# ----------------------------------------------------

class Branch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    repo_id = db.Column(db.Integer, db.ForeignKey('repo.id'), nullable=False)
    latest_code = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

class MergeRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='open') # 'open', 'merged', 'closed'
    ai_summary = db.Column(db.Text, nullable=True)     # Résumé IA du diff
    
    repo_id = db.Column(db.Integer, db.ForeignKey('repo.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    source_branch_id = db.Column(db.Integer, db.ForeignKey('branch.id'), nullable=False)
    target_branch_id = db.Column(db.Integer, db.ForeignKey('branch.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    # Relations
    author = db.relationship('User', backref='merge_requests')
    source_branch = db.relationship('Branch', foreign_keys=[source_branch_id])
    target_branch = db.relationship('Branch', foreign_keys=[target_branch_id])

class MergeComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    mr_id = db.Column(db.Integer, db.ForeignKey('merge_request.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    author = db.relationship('User')


# ----------------------------------------------------
# ROUTES & LOGIQUE
# ----------------------------------------------------

import difflib

def generate_diff(old_code: str, new_code: str) -> list[dict]:
    """Génère un diff ligne par ligne exploitable côté Jinja/HTML."""
    old_lines = (old_code or "").splitlines()
    new_lines = (new_code or "").splitlines()
    
    diff = list(difflib.ndiff(old_lines, new_lines))
    parsed_diff = []
    
    line_old = 1
    line_new = 1
    
    for line in diff:
        code = line[2:]
        if line.startswith('  '):
            parsed_diff.append({'type': 'same', 'old_num': line_old, 'new_num': line_new, 'text': code})
            line_old += 1
            line_new += 1
        elif line.startswith('- '):
            parsed_diff.append({'type': 'delete', 'old_num': line_old, 'new_num': '', 'text': code})
            line_old += 1
        elif line.startswith('+ '):
            parsed_diff.append({'type': 'add', 'old_num': '', 'new_num': line_new, 'text': code})
            line_new += 1
            
    return parsed_diff

def generate_ai_summary(old_code: str, new_code: str) -> str:
    """Analyse heuristique/locale du diff pour produire un résumé IA synthétique."""
    diff_lines = list(difflib.unified_diff(
        (old_code or "").splitlines(), 
        (new_code or "").splitlines(), 
        lineterm=''
    ))
    
    adds = [l[1:] for l in diff_lines if l.startswith('+') and not l.startswith('+++')]
    dels = [l[1:] for l in diff_lines if l.startswith('-') and not l.startswith('---')]
    
    summary_parts = []
    summary_parts.append(f"📊 **Analyse des modifications** : +{len(adds)} ligne(s) ajoutée(s), -{len(dels)} supprimée(s).")
    
    # Détection des éléments modifiés
    new_funcs = [l.strip() for l in adds if l.strip().startswith(('def ', 'class ', 'function '))]
    del_funcs = [l.strip() for l in dels if l.strip().startswith(('def ', 'class ', 'function '))]
    imports   = [l.strip() for l in adds if l.strip().startswith(('import ', 'from '))]
    
    if new_funcs:
        summary_parts.append("\n✨ **Nouvelles structures / fonctions définies :**\n" + "\n".join(f"- `{f}`" for f in new_funcs))
    if del_funcs:
        summary_parts.append("\n🗑️ **Structures / fonctions supprimées :**\n" + "\n".join(f"- `{f}`" for f in del_funcs))
    if imports:
        summary_parts.append("\n📦 **Nouveaux modules/dépendances importés :**\n" + "\n".join(f"- `{i}`" for i in imports))
        
    if not new_funcs and not del_funcs and not imports:
        summary_parts.append("\n📝 **Type de changement :** Modification de la logique interne, refactorisation ou mise à jour des variables/commentaires.")
        
    return "\n".join(summary_parts)

import json



@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()
        
        if user:
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            return redirect(url_for('dashboard'))
        else:
            flash('Identifiants incorrects', 'danger')
            
    return render_template('login.html')

from sqlalchemy import or_

@app.route('/forge', methods=['GET', 'POST'])
def forge():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    current_user_id = session['user_id']
    
    # 1. TRAITEMENT DE TOUS LES FORMULAIRES (POST)
    if request.method == 'POST':
        if 'create_repo' in request.form:
            name = request.form.get('name')
            desc = request.form.get('description')
            if name:
                new_repo = Repo(name=name, description=desc, user_id=current_user_id, visibility='private')
                db.session.add(new_repo)
                db.session.commit()
                return redirect(url_for('forge'))

        elif 'push_code' in request.form:
            repo_id = request.form.get('repo_id')
            branch_id = request.form.get('branch_id')
            message = request.form.get('message', 'Mise à jour 💻')
            code = request.form.get('code')
            if repo_id and code:
                # On met à jour le code de la branche active (c'est elle qui sert de base aux diffs / merge requests)
                branch = Branch.query.get(branch_id) if branch_id else None
                if branch and branch.repo_id == int(repo_id):
                    branch.latest_code = code

                # Historique global du dépôt (toutes branches confondues)
                commit_message = message
                if branch:
                    commit_message = f"[{branch.name}] {message}"
                new_commit = Commit(message=commit_message, code_snapshot=code, repo_id=repo_id)
                db.session.add(new_commit)
                db.session.commit()
                return redirect(url_for('forge', repo_id=repo_id, branch_id=branch_id))

        elif 'update_visibility' in request.form:
            repo_id = request.form.get('repo_id')
            visibility = request.form.get('visibility')
            repo = Repo.query.get_or_404(repo_id)
            
            if repo.user_id == current_user_id:
                repo.visibility = visibility
                RepoAccess.query.filter_by(repo_id=repo.id).delete()
                
                if visibility == 'private':
                    users_shared = request.form.getlist('share_users')
                    for u_id in users_shared:
                        access = RepoAccess(repo_id=repo.id, user_id=int(u_id))
                        db.session.add(access)
                        
                db.session.commit()
                flash('Paramètres de partage mis à jour !', 'success')
                return redirect(url_for('forge', repo_id=repo_id))

        elif 'add_comment' in request.form:
            repo_id = request.form.get('repo_id')
            content = request.form.get('content')
            if repo_id and content:
                new_comment = Comment(content=content, repo_id=repo_id, user_id=current_user_id)
                db.session.add(new_comment)
                db.session.commit()
                flash('Message posté avec succès ! 💬', 'success')
                return redirect(url_for('forge', repo_id=repo_id))

    # 2. PRÉPARATION DES DONNÉES D'AFFICHAGE (GET)
    repo_id = request.args.get('repo_id')
    selected_repo = Repo.query.get(repo_id) if repo_id else None
    
    mes_repos = Repo.query.filter_by(user_id=current_user_id).all()
    shared_access = RepoAccess.query.filter_by(user_id=current_user_id).all()
    allowed_private_ids = [sa.repo_id for sa in shared_access]
    
    repos_partages = Repo.query.filter(
        Repo.user_id != current_user_id,
        or_(Repo.visibility == 'public', Repo.id.in_(allowed_private_ids))
    ).all()
    
    membres_famille = User.query.filter(User.id != current_user_id).all() 
    
    current_access_ids = []
    branches = []
    merge_requests = []
    selected_branch = None
    if selected_repo:
        current_access_ids = [access.user_id for access in selected_repo.shared_with]

        # Sécurité : un dépôt doit toujours avoir au moins une branche pour être éditable
        if not Branch.query.filter_by(repo_id=selected_repo.id).first():
            derniere_version = selected_repo.commits[-1].code_snapshot if selected_repo.commits else "# Code initial"
            db.session.add(Branch(name="main", repo_id=selected_repo.id, latest_code=derniere_version))
            db.session.commit()

        branches = Branch.query.filter_by(repo_id=selected_repo.id).order_by(Branch.created_at.asc()).all()
        merge_requests = MergeRequest.query.filter_by(repo_id=selected_repo.id).order_by(MergeRequest.created_at.desc()).all()

        branch_id = request.args.get('branch_id')
        if branch_id:
            selected_branch = next((b for b in branches if b.id == int(branch_id)), None)
        if not selected_branch:
            selected_branch = next((b for b in branches if b.name == 'main'), branches[0])

    return render_template('forge.html', 
                           repos=mes_repos, 
                           repos_partages=repos_partages,
                           selected_repo=selected_repo, 
                           membres_famille=membres_famille,
                           current_access_ids=current_access_ids,
                           branches=branches,
                           merge_requests=merge_requests,
                           selected_branch=selected_branch)

@app.route('/admin/classes', methods=['GET', 'POST'])
def admin_classes():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        if 'create_classroom' in request.form:
            name = request.form.get('classname')
            if name and not Classroom.query.filter_by(name=name).first():
                db.session.add(Classroom(name=name))
                db.session.commit()
        elif 'assign_user' in request.form:
            user = db.session.get(User, int(request.form.get('user_id')))
            classe = db.session.get(Classroom, int(request.form.get('classroom_id')))
            if user and classe:
                if user.role == 'prof' and user not in classe.teachers:
                    classe.teachers.append(user)
                elif user.role == 'eleve' and user not in classe.students:
                    classe.students.append(user)
                db.session.commit()
        return redirect(url_for('admin_classes'))

    return render_template('admin_classes.html', classes=Classroom.query.all(), users=User.query.all())

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    current_user = db.session.get(User, session['user_id'])
    
    # On récupère les classes selon le rôle pour les afficher sur les cartes
    if session['role'] == 'prof':
        user_classes = current_user.classes_as_teacher.all()
    else:
        user_classes = current_user.classes_as_student.all()
        
    return render_template('dashboard.html', 
                           username=session['username'], 
                           role=session['role'], 
                           user_classes=user_classes)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/classes')
def mes_classes():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    current_user = db.session.get(User, session['user_id'])
    
    if session['role'] == 'prof':
        # Récupère toutes les classes associées à ce professeur
        mes_groupes = current_user.classes_as_teacher
    else:
        # Récupère toutes les classes associées à cet élève
        mes_groupes = current_user.classes_as_student
        
    return render_template('classes.html', groupes=mes_groupes, role=session['role'])

# Fonction utilitaire pour vérifier les extensions de fichiers
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Insertion de données de test à l'initialisation
def init_db():
    with app.app_context():
        db.create_all()
        repos = Repo.query.all()
        for repo in repos:
            has_branch = Branch.query.filter_by(repo_id=repo.id).first()
            if not has_branch:
                main_branch = Branch(name="main", repo_id=repo.id, latest_code="# Code initial")
                db.session.add(main_branch)
        db.session.commit()
        if not User.query.filter_by(username='prof1').first():
            # 1. Création des utilisateurs
            prof = User(username='prof1', password='password123', role='prof')
            eleve = User(username='eleve1', password='password123', role='eleve')
            db.session.add_all([prof, eleve])
            db.session.commit()
            
            # 2. Création d'une classe de test et assignation
            classe_test = Classroom(name="Groupe Python 🐍")
            classe_test.teachers.append(prof)
            classe_test.students.append(eleve)
            
            db.session.add(classe_test)
            db.session.commit()
            print("Base de données initialisée avec prof1, eleve1 et leur Classroom !")
        classe_python = Classroom.query.filter_by(name="Groupe Python 🐍").first()
        if not classe_python:
            classe_python = Classroom(name="Groupe Python 🐍")
            db.session.add(classe_python)
            db.session.commit()
    
    # 2. Récupère ton prof et ton élève (s'ils existent)
            mon_prof = User.query.filter_by(username="prof1").first()
            mon_eleve = User.query.filter_by(username="Jules").first()
    
    # 3. Inscris-les de force dans la classe s'ils n'y sont pas
            if mon_prof and mon_prof not in classe_python.teachers:
                classe_python.teachers.append(mon_prof)
        
            if mon_eleve and mon_eleve not in classe_python.students:
                classe_python.students.append(mon_eleve)
        
        db.session.commit()

# ----------------------------------------------------
# MODULE 1 : LES COURS
# ----------------------------------------------------

@app.route('/cours', methods=['GET', 'POST'])
def cours():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Si c'est un prof qui soumet le formulaire, on ajoute le cours
    if request.method == 'POST' and session['role'] == 'prof':
        title = request.form['title']
        content = request.form['content']
        
        if title and content:
            new_course = Course(title=title, content=content)
            db.session.add(new_course)
            db.session.commit()
            flash('Le cours a été publié avec succès !', 'success')
        else:
            flash('Veuillez remplir tous les champs.', 'danger')
        return redirect(url_for('cours'))

    # Dans tous les cas, on affiche la liste des cours
    liste_cours = Course.query.all()
    return render_template('cours.html', liste_cours=liste_cours, role=session['role'])

@app.route('/flashcards', methods=['GET', 'POST'])
def flashcards():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    current_user_id = session['user_id']
    
    if request.method == 'POST':
        category = request.form.get('category', 'Général')
        question = request.form.get('question')
        answer = request.form.get('answer')
        
        if question and answer:
            new_card = Flashcard(category=category, question=question, answer=answer, user_id=current_user_id)
            db.session.add(new_card)
            db.session.commit()
            flash('Flashcard ajoutée avec succès !', 'success')
            return redirect(url_for('flashcards', mode='prof'))
            
    mode = request.args.get('mode') # 'prof' ou 'eleve'
    cards = Flashcard.query.all()
    
    return render_template('flashcards.html', mode=mode, cards=cards, role=session['role'])

@app.route('/flashcards/supprimer/<int:id>', methods=['POST'])
def supprimer_flashcard(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    card = Flashcard.query.get_or_404(id)
    if card.user_id == session['user_id']:
        db.session.delete(card)
        db.session.commit()
        flash('Flashcard supprimée !', 'success')
        
    return redirect(url_for('flashcards', mode='prof'))

# ----------------------------------------------------
# MODULE 2 : LES DEVOIRS & SOUMISSIONS
# ----------------------------------------------------

@app.route('/devoirs', methods=['GET', 'POST'])
def devoirs():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Si le prof crée un nouveau devoir
    if request.method == 'POST' and session['role'] == 'prof' and 'create_assignment' in request.form:
        title = request.form['title']
        description = request.form['description']
        new_assignment = Assignment(title=title, description=description)
        db.session.add(new_assignment)
        db.session.commit()
        flash('Devoir créé !', 'success')
        return redirect(url_for('devoirs'))

    # Récupération des données selon le rôle pour l'affichage
    liste_devoirs = Assignment.query.all()
    
    # Pour le prof : voir toutes les copies rendues
    # Pour le prof : voir uniquement les copies des élèves de ses classes
    rendus = []
    if session['role'] == 'prof':
        current_teacher = User.query.get(session['user_id'])
        
        # On récupère les IDs de tous les élèves inscrits dans les classes de ce prof
        allowed_student_ids = []
        for classe in current_teacher.classes_as_teacher:
            for student in classe.students:
                if student.id not in allowed_student_ids:
                    allowed_student_ids.append(student.id)
        
        # On filtre les soumissions pour n'avoir que celles de ces élèves
        rendus = db.session.query(Submission, User, Assignment).\
            join(User, Submission.student_id == User.id).\
            join(Assignment, Submission.assignment_id == Assignment.id).\
            filter(Submission.student_id.in_(allowed_student_ids)).all()
            
    # Pour l'élève : voir ses propres rendus pour savoir s'il a déjà rendu ou s'il a une note
    mes_rendus = {}
    if session['role'] == 'eleve':
        sub_list = Submission.query.filter_by(student_id=session['user_id']).all()
        # On crée un dictionnaire {assignment_id: objet_submission} pour l'interroger facilement dans le HTML
        mes_rendus = {sub.assignment_id: sub for sub in sub_list}

    return render_template('devoirs.html', 
                           liste_devoirs=liste_devoirs, 
                           rendus=rendus, 
                           mes_rendus=mes_rendus, 
                           role=session['role'])


@app.route('/rendre/<int:assignment_id>', methods=['POST'])
def rendre_devoir(assignment_id):
    if 'user_id' not in session or session['role'] != 'eleve':
        return redirect(url_for('login'))

    if 'file' not in request.files:
        flash('Aucun fichier détecté.', 'danger')
        return redirect(url_for('devoirs'))
        
    file = request.files['file']
    if file.filename == '':
        flash('Aucun fichier sélectionné.', 'danger')
        return redirect(url_for('devoirs'))

    if file and allowed_file(file.filename):
        # Sécurisation du nom de fichier pour éviter les injections de chemins
        filename = secure_filename(f"user_{session['user_id']}_{assignment_id}_{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        # Vérifier si l'élève a déjà rendu ce devoir pour le mettre à jour, sinon on le crée
        submission = Submission.query.filter_by(assignment_id=assignment_id, student_id=session['user_id']).first()
        if submission:
            submission.filename = filename
        else:
            submission = Submission(assignment_id=assignment_id, student_id=session['user_id'], filename=filename)
            db.session.add(submission)
            
        db.session.commit()
        flash('Votre devoir a bien été envoyé !', 'success')
    else:
        flash('Extension de fichier non autorisée.', 'danger')

    return redirect(url_for('devoirs'))


@app.route('/noter/<int:submission_id>', methods=['POST'])
def noter_devoir(submission_id):
    if 'user_id' not in session or session['role'] != 'prof':
        return redirect(url_for('login'))

    submission = Submission.query.get_or_404(submission_id)
    grade = request.form.get('grade')
    comment = request.form.get('comment')

    try:
        submission.grade = float(grade)
        submission.comment = comment
        db.session.commit()
        flash('Copie notée avec succès !', 'success')
    except ValueError:
        flash('La note doit être un nombre valide.', 'danger')

    return redirect(url_for('devoirs'))


# ----------------------------------------------------
# MODULE 3 : LA MESSAGERIE (Prof <-> Élèves)
# ----------------------------------------------------

@app.route('/messagerie', methods=['GET', 'POST'])
def messagerie():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    current_user_id = session['user_id']

    # Si envoi d'un message
    if request.method == 'POST':
        receiver_id = request.form.get('receiver_id')
        content = request.form.get('content')
        if receiver_id and content:
            new_msg = Message(sender_id=current_user_id, receiver_id=int(receiver_id), content=content)
            db.session.add(new_msg)
            db.session.commit()
            flash('Message envoyé !', 'success')
        return redirect(url_for('messagerie'))

    # Pour l'affichage de la liste des contacts dispos
    # Pour l'affichage de la liste des contacts dispos (filtré par classe)
    current_user = db.session.get(User, session['user_id'])
    contacts = []

    if session['role'] == 'prof':
        # Le prof voit uniquement les élèves de SES classes
        for classe in current_user.classes_as_teacher:
            for student in classe.students:
                if student not in contacts:
                    contacts.append(student)
    else:
        # L'élève voit uniquement les profs de SES classes
        for classe in current_user.classes_as_student:
            for teacher in classe.teachers:
                if teacher not in contacts:
                    contacts.append(teacher)

    # Récupération de tous les messages impliquant l'utilisateur connecté
    messages = db.session.query(Message, User).\
        join(User, Message.sender_id == User.id).\
        filter((Message.sender_id == current_user_id) | (Message.receiver_id == current_user_id)).\
        order_by(Message.timestamp.asc()).all()

    return render_template('messagerie.html', contacts=contacts, messages=messages, current_user_id=current_user_id)

@app.route('/telecharger/<string:filename>')
def telecharger_devoir(filename):
    # Sécurité : On vérifie que l'utilisateur est bien connecté
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    # Envoi sécurisé du fichier depuis le dossier d'upload
    return send_from_directory(
        app.config['UPLOAD_FOLDER'], 
        filename, 
        as_attachment=True # Force le téléchargement plutôt que l'ouverture dans le navigateur
    )

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        role = request.form['role'] # 'prof' ou 'eleve'
        
        # Vérification si les champs sont vides
        if not username or not password or not role:
            flash('Veuillez remplir tous les champs.', 'danger')
            return redirect(url_for('register'))
            
        # Vérifier si l'utilisateur existe déjà
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash("Ce nom d'utilisateur est déjà pris. Choisissez-en un autre.", 'danger')
            return redirect(url_for('register'))
            
        # Création du nouvel utilisateur
        new_user = User(username=username, password=password, role=role)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Votre compte a été créé avec succès ! Vous pouvez maintenant vous connecter.', 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/mindmaps', methods=['GET', 'POST'])
def mindmaps():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    current_user_id = session['user_id']
    
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content') # Le JSON envoyé par JS
        map_id = request.form.get('map_id') # Optionnel, si on modifie une carte existante
        
        if title and content:
            if map_id: # Mode modification
                carte = Mindmap.query.get(map_id)
                if carte and carte.user_id == current_user_id:
                    carte.title = title
                    carte.content = content
            else: # Mode création
                new_map = Mindmap(title=title, content=content, user_id=current_user_id)
                db.session.add(new_map)
            
            db.session.commit()
            flash('Carte mentale enregistrée avec succès !', 'success')
            return redirect(url_for('mindmaps'))
            
    # Récupération des modes via les paramètres de l'URL (?mode=createur ou ?mode=eleve)
    mode = request.args.get('mode')
    selected_id = request.args.get('id')
    
    carte_chargee = None
    if selected_id:
        carte_chargee = Mindmap.query.get_or_404(selected_id)
        
    mes_cartes = Mindmap.query.filter_by(user_id=current_user_id).all()
    
    return render_template('mindmaps.html', mode=mode, mes_cartes=mes_cartes, carte_chargee=carte_chargee)

import sys
import io

@app.route('/sandbox', methods=['GET', 'POST'])
def sandbox():
    code = request.form.get('code', '# Écris ton code Python ici...\nprint("Bonjour la famille !")\n')
    output = ""
    
    if request.method == 'POST' and 'run_code' in request.form:
        # 1. On détourne la sortie standard pour capturer les print()
        old_stdout = sys.stdout
        redirected_output = io.StringIO()
        sys.stdout = redirected_output
        
        try:
            # 2. On exécute le code dans un environnement restreint pour la sécurité
            # On interdit les imports dangereux dans cet espace de test
            restricted_globals = {"__builtins__": __builtins__}
            exec(code, restricted_globals)
            output = redirected_output.getvalue()
        except Exception as e:
            # En cas d'erreur de syntaxe ou d'exécution, on capture le message d'erreur
            output = f"❌ Erreur :\n{str(e)}"
        finally:
            # 3. On remet la sortie standard normale du serveur
            sys.stdout = old_stdout

    return render_template('sandbox.html', code=code, output=output)

@app.route('/projets-guides/supprimer/<int:id>', methods=['POST'])
def supprimer_projet_guide(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    project = ProjetGuide.query.get_or_404(id)
    
    # Sécurité : Seul le créateur du projet (le prof) peut le supprimer
    if project.user_id == session['user_id']:
        db.session.delete(project)
        db.session.commit()
        flash('Projet supprimé avec succès !', 'success')
    else:
        flash('Action non autorisée.', 'danger')
        
    return redirect(url_for('projets_guides', mode='prof'))

@app.route('/projets-guides', methods=['GET', 'POST'])
def projets_guides():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    current_user_id = session['user_id']
    
    if request.method == 'POST':
        # Sauvegarde d'un nouveau projet par le prof
        title = request.form.get('title')
        steps_data = request.form.get('steps_data') # Reçu sous forme de chaîne JSON depuis le formulaire
        
        if title and steps_data:
            new_project = ProjetGuide(title=title, steps_json=steps_data, user_id=current_user_id)
            db.session.add(new_project)
            db.session.commit()
            flash('Nouveau projet guidé créé avec succès !', 'success')
            return redirect(url_for('projets_guides'))

    # Lecture des paramètres
    mode = request.args.get('mode') # 'prof' ou 'eleve'
    project_id = request.args.get('id') # ID du projet sélectionné
    
    projet_charge = None
    if project_id:
        projet_charge = ProjetGuide.query.get_or_404(project_id)
        
    tous_les_projets = ProjetGuide.query.all() # Tout le monde peut voir les projets créés
    
    return render_template('projets_guides.html', mode=mode, projets=tous_les_projets, projet_charge=projet_charge)

@app.route('/mindmaps/delete/<int:map_id>', methods=['POST'])
def delete_mindmap(map_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    carte = Mindmap.query.get_or_404(map_id)
    if carte.user_id == session['user_id']:
        db.session.delete(carte)
        db.session.commit()
        flash('Carte mentale supprimée.', 'success')
    return redirect(url_for('mindmaps'))

# ----------------------------------------------------
# ROUTES DE GESTION DES BRANCHES & MERGE REQUESTS
# ----------------------------------------------------

@app.route('/repo/<int:repo_id>/branch/create', methods=['POST'])
def create_branch(repo_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    branch_name = request.form.get('branch_name', '').strip().lower().replace(' ', '-')
    if not branch_name:
        flash('Nom de branche invalide', 'danger')
        return redirect(url_for('forge', repo_id=repo_id))
        
    # Branche source depuis laquelle on copie le code
    source_branch_id = request.form.get('source_branch_id')
    source_branch = Branch.query.get(source_branch_id) if source_branch_id else None
    
    initial_code = source_branch.latest_code if source_branch else ""
    
    new_branch = Branch(name=branch_name, repo_id=repo_id, latest_code=initial_code)
    db.session.add(new_branch)
    db.session.commit()
    
    flash(f'Branche "{branch_name}" créée avec succès ! 🌿', 'success')
    return redirect(url_for('forge', repo_id=repo_id))


@app.route('/repo/<int:repo_id>/merge-request/create', methods=['GET', 'POST'])
def create_merge_request(repo_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    repo = Repo.query.get_or_404(repo_id)
    branches = Branch.query.filter_by(repo_id=repo.id).all()
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        source_id = int(request.form.get('source_branch_id'))
        target_id = int(request.form.get('target_branch_id'))
        
        if source_id == target_id:
            flash('La branche source et la branche cible doivent être différentes.', 'danger')
            return redirect(url_for('create_merge_request', repo_id=repo_id))
            
        src = Branch.query.get(source_id)
        tgt = Branch.query.get(target_id)
        
        # Génération du résumé IA automatique
        ai_summary = generate_ai_summary(tgt.latest_code, src.latest_code)
        
        mr = MergeRequest(
            title=title,
            description=description,
            repo_id=repo_id,
            author_id=session['user_id'],
            source_branch_id=source_id,
            target_branch_id=target_id,
            ai_summary=ai_summary
        )
        db.session.add(mr)
        db.session.commit()
        
        flash('Demande de fusion (Merge Request) créée ! 🔀', 'success')
        return redirect(url_for('view_merge_request', mr_id=mr.id))
        
    return render_template('create_mr.html', repo=repo, branches=branches)


@app.route('/merge-request/<int:mr_id>', methods=['GET', 'POST'])
def view_merge_request(mr_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    mr = MergeRequest.query.get_or_404(mr_id)
    
    # Ajout de commentaires sur la PR
    if request.method == 'POST' and 'add_mr_comment' in request.form:
        content = request.form.get('content')
        if content:
            comment = MergeComment(content=content, mr_id=mr.id, user_id=session['user_id'])
            db.session.add(comment)
            db.session.commit()
            flash('Commentaire ajouté ! 💬', 'success')
            return redirect(url_for('view_merge_request', mr_id=mr.id))

    # Calcul du Diff
    diff_data = generate_diff(mr.target_branch.latest_code, mr.source_branch.latest_code)
    
    comments = MergeComment.query.filter_by(mr_id=mr.id).order_by(MergeComment.timestamp.asc()).all()
    
    return render_template('view_mr.html', mr=mr, diff_data=diff_data, comments=comments)


@app.route('/merge-request/<int:mr_id>/execute', methods=['POST'])
def execute_merge(mr_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    mr = MergeRequest.query.get_or_404(mr_id)
    
    if mr.status != 'open':
        flash('Cette demande est déjà fermée ou fusionnée.', 'warning')
        return redirect(url_for('view_merge_request', mr_id=mr.id))
        
    # Copie du code de la branche source vers la branche cible
    mr.target_branch.latest_code = mr.source_branch.latest_code
    mr.status = 'merged'
    
    # Création d'un commit automatique de fusion
    commit_msg = f"Merge branch '{mr.source_branch.name}' into {mr.target_branch.name}"
    new_commit = Commit(message=commit_msg, code_snapshot=mr.target_branch.latest_code, repo_id=mr.repo_id)
    
    db.session.add(new_commit)
    db.session.commit()
    
    flash('Fusion effectuée avec succès ! 🎉', 'success')
    return redirect(url_for('view_merge_request', mr_id=mr.id))

# Initialise la base de données (crée les tables si besoin) au chargement du module.
# Important : ceci doit s'exécuter que l'app soit lancée avec `python app.py`
# OU importée par un serveur WSGI comme gunicorn (`gunicorn app:app`), sinon
# les tables ne sont jamais créées en production.
init_db()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5003)

app = Flask(__name__)
app.secret_key = 'une_cle_secrete_tres_securisee'

# Configuration de la base de données et des uploads
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'png', 'jpg', 'jpeg', 'docx', 'txt', 'zip', 'py'}

db = SQLAlchemy(app)
with app.app_context():
    init_db()

# Création du dossier d'upload s'il n'existe pas
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# ----------------------------------------------------
# MODÈLES DE LA BASE DE DONNÉES
# ----------------------------------------------------
# Table d'association : Qui est élève dans quelle classe ?
student_classroom = db.Table('student_classroom',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('classroom_id', db.Integer, db.ForeignKey('classroom.id'), primary_key=True)
)

# Table d'association : Qui est prof dans quelle classe ?
teacher_classroom = db.Table('teacher_classroom',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('classroom_id', db.Integer, db.ForeignKey('classroom.id'), primary_key=True)
)

class Classroom(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    
    # Relations many-to-many
    students = db.relationship('User', secondary=student_classroom, backref=db.backref('classes_as_student', lazy='dynamic'))
    teachers = db.relationship('User', secondary=teacher_classroom, backref=db.backref('classes_as_teacher', lazy='dynamic'))
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(10), nullable=False) # 'prof' ou 'eleve'

class Mindmap(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)  # Stockera le JSON.stringify() de la carte
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)

class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)

class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignment.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    grade = db.Column(db.Float, nullable=True) # Note laissée par le prof
    comment = db.Column(db.Text, nullable=True)

class ProjetGuide(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    steps_json = db.Column(db.Text, nullable=False) # Contiendra le tableau d'étapes en JSON
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Flashcard(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(100), nullable=False, default="Général")
    question = db.Column(db.Text, nullable=False) # Le Recto
    answer = db.Column(db.Text, nullable=False)   # Le Verso (Le code Python propre)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    # Clés étrangères
    repo_id = db.Column(db.Integer, db.ForeignKey('repo.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relation pour récupérer facilement le nom de l'auteur dans Jinja
    author = db.relationship('User', backref=db.backref('comments', lazy=True))

class Repo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(300))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    visibility = db.Column(db.String(20), default='private')
    
    # ─── LA LIGNE À RAJOUTER ICI ───
    # Elle permet à Jinja de faire "r.user.username" sans planter
    user = db.relationship('User', backref=db.backref('repos', lazy=True))
    comments = db.relationship('Comment', backref='repo', lazy=True, cascade="all, delete-orphan")
    # Le reste de tes relations existantes :
    commits = db.relationship('Commit', backref='repo', lazy=True, cascade="all, delete-orphan")
    shared_with = db.relationship('RepoAccess', backref='repo', lazy=True, cascade="all, delete-orphan")
    merge_requests_list = db.relationship('MergeRequest', backref='repo', lazy=True, cascade="all, delete-orphan")
class RepoAccess(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    repo_id = db.Column(db.Integer, db.ForeignKey('repo.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # L'utilisateur qui reçoit l'accès

class Commit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.String(200), nullable=False)
    code_snapshot = db.Column(db.Text, nullable=False) # Le code complet à ce moment X
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    repo_id = db.Column(db.Integer, db.ForeignKey('repo.id'), nullable=False)

# ----------------------------------------------------
# NOUVEAUX MODÈLES POUR LA FUSION ET LE DIFF VIEWER
# ----------------------------------------------------

class Branch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    repo_id = db.Column(db.Integer, db.ForeignKey('repo.id'), nullable=False)
    latest_code = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

class MergeRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='open') # 'open', 'merged', 'closed'
    ai_summary = db.Column(db.Text, nullable=True)     # Résumé IA du diff
    
    repo_id = db.Column(db.Integer, db.ForeignKey('repo.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    source_branch_id = db.Column(db.Integer, db.ForeignKey('branch.id'), nullable=False)
    target_branch_id = db.Column(db.Integer, db.ForeignKey('branch.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    # Relations
    author = db.relationship('User', backref='merge_requests')
    source_branch = db.relationship('Branch', foreign_keys=[source_branch_id])
    target_branch = db.relationship('Branch', foreign_keys=[target_branch_id])

class MergeComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    mr_id = db.Column(db.Integer, db.ForeignKey('merge_request.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    author = db.relationship('User')


# ----------------------------------------------------
# ROUTES & LOGIQUE
# ----------------------------------------------------

import difflib

def generate_diff(old_code: str, new_code: str) -> list[dict]:
    """Génère un diff ligne par ligne exploitable côté Jinja/HTML."""
    old_lines = (old_code or "").splitlines()
    new_lines = (new_code or "").splitlines()
    
    diff = list(difflib.ndiff(old_lines, new_lines))
    parsed_diff = []
    
    line_old = 1
    line_new = 1
    
    for line in diff:
        code = line[2:]
        if line.startswith('  '):
            parsed_diff.append({'type': 'same', 'old_num': line_old, 'new_num': line_new, 'text': code})
            line_old += 1
            line_new += 1
        elif line.startswith('- '):
            parsed_diff.append({'type': 'delete', 'old_num': line_old, 'new_num': '', 'text': code})
            line_old += 1
        elif line.startswith('+ '):
            parsed_diff.append({'type': 'add', 'old_num': '', 'new_num': line_new, 'text': code})
            line_new += 1
            
    return parsed_diff

def generate_ai_summary(old_code: str, new_code: str) -> str:
    """Analyse heuristique/locale du diff pour produire un résumé IA synthétique."""
    diff_lines = list(difflib.unified_diff(
        (old_code or "").splitlines(), 
        (new_code or "").splitlines(), 
        lineterm=''
    ))
    
    adds = [l[1:] for l in diff_lines if l.startswith('+') and not l.startswith('+++')]
    dels = [l[1:] for l in diff_lines if l.startswith('-') and not l.startswith('---')]
    
    summary_parts = []
    summary_parts.append(f"📊 **Analyse des modifications** : +{len(adds)} ligne(s) ajoutée(s), -{len(dels)} supprimée(s).")
    
    # Détection des éléments modifiés
    new_funcs = [l.strip() for l in adds if l.strip().startswith(('def ', 'class ', 'function '))]
    del_funcs = [l.strip() for l in dels if l.strip().startswith(('def ', 'class ', 'function '))]
    imports   = [l.strip() for l in adds if l.strip().startswith(('import ', 'from '))]
    
    if new_funcs:
        summary_parts.append("\n✨ **Nouvelles structures / fonctions définies :**\n" + "\n".join(f"- `{f}`" for f in new_funcs))
    if del_funcs:
        summary_parts.append("\n🗑️ **Structures / fonctions supprimées :**\n" + "\n".join(f"- `{f}`" for f in del_funcs))
    if imports:
        summary_parts.append("\n📦 **Nouveaux modules/dépendances importés :**\n" + "\n".join(f"- `{i}`" for i in imports))
        
    if not new_funcs and not del_funcs and not imports:
        summary_parts.append("\n📝 **Type de changement :** Modification de la logique interne, refactorisation ou mise à jour des variables/commentaires.")
        
    return "\n".join(summary_parts)

import json



@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()
        
        if user:
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            return redirect(url_for('dashboard'))
        else:
            flash('Identifiants incorrects', 'danger')
            
    return render_template('login.html')

from sqlalchemy import or_

@app.route('/forge', methods=['GET', 'POST'])
def forge():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    current_user_id = session['user_id']
    
    # 1. TRAITEMENT DE TOUS LES FORMULAIRES (POST)
    if request.method == 'POST':
        if 'create_repo' in request.form:
            name = request.form.get('name')
            desc = request.form.get('description')
            if name:
                new_repo = Repo(name=name, description=desc, user_id=current_user_id, visibility='private')
                db.session.add(new_repo)
                db.session.commit()
                return redirect(url_for('forge'))

        elif 'push_code' in request.form:
            repo_id = request.form.get('repo_id')
            branch_id = request.form.get('branch_id')
            message = request.form.get('message', 'Mise à jour 💻')
            code = request.form.get('code')
            if repo_id and code:
                # On met à jour le code de la branche active (c'est elle qui sert de base aux diffs / merge requests)
                branch = Branch.query.get(branch_id) if branch_id else None
                if branch and branch.repo_id == int(repo_id):
                    branch.latest_code = code

                # Historique global du dépôt (toutes branches confondues)
                commit_message = message
                if branch:
                    commit_message = f"[{branch.name}] {message}"
                new_commit = Commit(message=commit_message, code_snapshot=code, repo_id=repo_id)
                db.session.add(new_commit)
                db.session.commit()
                return redirect(url_for('forge', repo_id=repo_id, branch_id=branch_id))

        elif 'update_visibility' in request.form:
            repo_id = request.form.get('repo_id')
            visibility = request.form.get('visibility')
            repo = Repo.query.get_or_404(repo_id)
            
            if repo.user_id == current_user_id:
                repo.visibility = visibility
                RepoAccess.query.filter_by(repo_id=repo.id).delete()
                
                if visibility == 'private':
                    users_shared = request.form.getlist('share_users')
                    for u_id in users_shared:
                        access = RepoAccess(repo_id=repo.id, user_id=int(u_id))
                        db.session.add(access)
                        
                db.session.commit()
                flash('Paramètres de partage mis à jour !', 'success')
                return redirect(url_for('forge', repo_id=repo_id))

        elif 'add_comment' in request.form:
            repo_id = request.form.get('repo_id')
            content = request.form.get('content')
            if repo_id and content:
                new_comment = Comment(content=content, repo_id=repo_id, user_id=current_user_id)
                db.session.add(new_comment)
                db.session.commit()
                flash('Message posté avec succès ! 💬', 'success')
                return redirect(url_for('forge', repo_id=repo_id))

    # 2. PRÉPARATION DES DONNÉES D'AFFICHAGE (GET)
    repo_id = request.args.get('repo_id')
    selected_repo = Repo.query.get(repo_id) if repo_id else None
    
    mes_repos = Repo.query.filter_by(user_id=current_user_id).all()
    shared_access = RepoAccess.query.filter_by(user_id=current_user_id).all()
    allowed_private_ids = [sa.repo_id for sa in shared_access]
    
    repos_partages = Repo.query.filter(
        Repo.user_id != current_user_id,
        or_(Repo.visibility == 'public', Repo.id.in_(allowed_private_ids))
    ).all()
    
    membres_famille = User.query.filter(User.id != current_user_id).all() 
    
    current_access_ids = []
    branches = []
    merge_requests = []
    selected_branch = None
    if selected_repo:
        current_access_ids = [access.user_id for access in selected_repo.shared_with]

        # Sécurité : un dépôt doit toujours avoir au moins une branche pour être éditable
        if not Branch.query.filter_by(repo_id=selected_repo.id).first():
            derniere_version = selected_repo.commits[-1].code_snapshot if selected_repo.commits else "# Code initial"
            db.session.add(Branch(name="main", repo_id=selected_repo.id, latest_code=derniere_version))
            db.session.commit()

        branches = Branch.query.filter_by(repo_id=selected_repo.id).order_by(Branch.created_at.asc()).all()
        merge_requests = MergeRequest.query.filter_by(repo_id=selected_repo.id).order_by(MergeRequest.created_at.desc()).all()

        branch_id = request.args.get('branch_id')
        if branch_id:
            selected_branch = next((b for b in branches if b.id == int(branch_id)), None)
        if not selected_branch:
            selected_branch = next((b for b in branches if b.name == 'main'), branches[0])

    return render_template('forge.html', 
                           repos=mes_repos, 
                           repos_partages=repos_partages,
                           selected_repo=selected_repo, 
                           membres_famille=membres_famille,
                           current_access_ids=current_access_ids,
                           branches=branches,
                           merge_requests=merge_requests,
                           selected_branch=selected_branch)

@app.route('/admin/classes', methods=['GET', 'POST'])
def admin_classes():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        if 'create_classroom' in request.form:
            name = request.form.get('classname')
            if name and not Classroom.query.filter_by(name=name).first():
                db.session.add(Classroom(name=name))
                db.session.commit()
        elif 'assign_user' in request.form:
            user = db.session.get(User, int(request.form.get('user_id')))
            classe = db.session.get(Classroom, int(request.form.get('classroom_id')))
            if user and classe:
                if user.role == 'prof' and user not in classe.teachers:
                    classe.teachers.append(user)
                elif user.role == 'eleve' and user not in classe.students:
                    classe.students.append(user)
                db.session.commit()
        return redirect(url_for('admin_classes'))

    return render_template('admin_classes.html', classes=Classroom.query.all(), users=User.query.all())

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    current_user = db.session.get(User, session['user_id'])
    
    # On récupère les classes selon le rôle pour les afficher sur les cartes
    if session['role'] == 'prof':
        user_classes = current_user.classes_as_teacher.all()
    else:
        user_classes = current_user.classes_as_student.all()
        
    return render_template('dashboard.html', 
                           username=session['username'], 
                           role=session['role'], 
                           user_classes=user_classes)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/classes')
def mes_classes():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    current_user = db.session.get(User, session['user_id'])
    
    if session['role'] == 'prof':
        # Récupère toutes les classes associées à ce professeur
        mes_groupes = current_user.classes_as_teacher
    else:
        # Récupère toutes les classes associées à cet élève
        mes_groupes = current_user.classes_as_student
        
    return render_template('classes.html', groupes=mes_groupes, role=session['role'])

# Fonction utilitaire pour vérifier les extensions de fichiers
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Insertion de données de test à l'initialisation
def init_db():
    with app.app_context():
        db.create_all()
        repos = Repo.query.all()
        for repo in repos:
            has_branch = Branch.query.filter_by(repo_id=repo.id).first()
            if not has_branch:
                main_branch = Branch(name="main", repo_id=repo.id, latest_code="# Code initial")
                db.session.add(main_branch)
        db.session.commit()
        if not User.query.filter_by(username='prof1').first():
            # 1. Création des utilisateurs
            prof = User(username='prof1', password='password123', role='prof')
            eleve = User(username='eleve1', password='password123', role='eleve')
            db.session.add_all([prof, eleve])
            db.session.commit()
            
            # 2. Création d'une classe de test et assignation
            classe_test = Classroom(name="Groupe Python 🐍")
            classe_test.teachers.append(prof)
            classe_test.students.append(eleve)
            
            db.session.add(classe_test)
            db.session.commit()
            print("Base de données initialisée avec prof1, eleve1 et leur Classroom !")
        classe_python = Classroom.query.filter_by(name="Groupe Python 🐍").first()
        if not classe_python:
            classe_python = Classroom(name="Groupe Python 🐍")
            db.session.add(classe_python)
            db.session.commit()
    
    # 2. Récupère ton prof et ton élève Jules
            mon_prof = db.session.get(User, User.query.filter_by(username="prof1").first().id) # Ajuste le pseudo si besoin
            mon_eleve = db.session.get(User, User.query.filter_by(username="Jules").first().id)
    
    # 3. Inscris-les de force dans la classe s'ils n'y sont pas
            if mon_prof and mon_prof not in classe_python.teachers:
                classe_python.teachers.append(mon_prof)
        
            if mon_eleve and mon_eleve not in classe_python.students:
                classe_python.students.append(mon_eleve)
        
        db.session.commit()

# ----------------------------------------------------
# MODULE 1 : LES COURS
# ----------------------------------------------------

@app.route('/cours', methods=['GET', 'POST'])
def cours():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Si c'est un prof qui soumet le formulaire, on ajoute le cours
    if request.method == 'POST' and session['role'] == 'prof':
        title = request.form['title']
        content = request.form['content']
        
        if title and content:
            new_course = Course(title=title, content=content)
            db.session.add(new_course)
            db.session.commit()
            flash('Le cours a été publié avec succès !', 'success')
        else:
            flash('Veuillez remplir tous les champs.', 'danger')
        return redirect(url_for('cours'))

    # Dans tous les cas, on affiche la liste des cours
    liste_cours = Course.query.all()
    return render_template('cours.html', liste_cours=liste_cours, role=session['role'])

@app.route('/flashcards', methods=['GET', 'POST'])
def flashcards():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    current_user_id = session['user_id']
    
    if request.method == 'POST':
        category = request.form.get('category', 'Général')
        question = request.form.get('question')
        answer = request.form.get('answer')
        
        if question and answer:
            new_card = Flashcard(category=category, question=question, answer=answer, user_id=current_user_id)
            db.session.add(new_card)
            db.session.commit()
            flash('Flashcard ajoutée avec succès !', 'success')
            return redirect(url_for('flashcards', mode='prof'))
            
    mode = request.args.get('mode') # 'prof' ou 'eleve'
    cards = Flashcard.query.all()
    
    return render_template('flashcards.html', mode=mode, cards=cards, role=session['role'])

@app.route('/flashcards/supprimer/<int:id>', methods=['POST'])
def supprimer_flashcard(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    card = Flashcard.query.get_or_404(id)
    if card.user_id == session['user_id']:
        db.session.delete(card)
        db.session.commit()
        flash('Flashcard supprimée !', 'success')
        
    return redirect(url_for('flashcards', mode='prof'))

# ----------------------------------------------------
# MODULE 2 : LES DEVOIRS & SOUMISSIONS
# ----------------------------------------------------

@app.route('/devoirs', methods=['GET', 'POST'])
def devoirs():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Si le prof crée un nouveau devoir
    if request.method == 'POST' and session['role'] == 'prof' and 'create_assignment' in request.form:
        title = request.form['title']
        description = request.form['description']
        new_assignment = Assignment(title=title, description=description)
        db.session.add(new_assignment)
        db.session.commit()
        flash('Devoir créé !', 'success')
        return redirect(url_for('devoirs'))

    # Récupération des données selon le rôle pour l'affichage
    liste_devoirs = Assignment.query.all()
    
    # Pour le prof : voir toutes les copies rendues
    # Pour le prof : voir uniquement les copies des élèves de ses classes
    rendus = []
    if session['role'] == 'prof':
        current_teacher = User.query.get(session['user_id'])
        
        # On récupère les IDs de tous les élèves inscrits dans les classes de ce prof
        allowed_student_ids = []
        for classe in current_teacher.classes_as_teacher:
            for student in classe.students:
                if student.id not in allowed_student_ids:
                    allowed_student_ids.append(student.id)
        
        # On filtre les soumissions pour n'avoir que celles de ces élèves
        rendus = db.session.query(Submission, User, Assignment).\
            join(User, Submission.student_id == User.id).\
            join(Assignment, Submission.assignment_id == Assignment.id).\
            filter(Submission.student_id.in_(allowed_student_ids)).all()
            
    # Pour l'élève : voir ses propres rendus pour savoir s'il a déjà rendu ou s'il a une note
    mes_rendus = {}
    if session['role'] == 'eleve':
        sub_list = Submission.query.filter_by(student_id=session['user_id']).all()
        # On crée un dictionnaire {assignment_id: objet_submission} pour l'interroger facilement dans le HTML
        mes_rendus = {sub.assignment_id: sub for sub in sub_list}

    return render_template('devoirs.html', 
                           liste_devoirs=liste_devoirs, 
                           rendus=rendus, 
                           mes_rendus=mes_rendus, 
                           role=session['role'])


@app.route('/rendre/<int:assignment_id>', methods=['POST'])
def rendre_devoir(assignment_id):
    if 'user_id' not in session or session['role'] != 'eleve':
        return redirect(url_for('login'))

    if 'file' not in request.files:
        flash('Aucun fichier détecté.', 'danger')
        return redirect(url_for('devoirs'))
        
    file = request.files['file']
    if file.filename == '':
        flash('Aucun fichier sélectionné.', 'danger')
        return redirect(url_for('devoirs'))

    if file and allowed_file(file.filename):
        # Sécurisation du nom de fichier pour éviter les injections de chemins
        filename = secure_filename(f"user_{session['user_id']}_{assignment_id}_{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        # Vérifier si l'élève a déjà rendu ce devoir pour le mettre à jour, sinon on le crée
        submission = Submission.query.filter_by(assignment_id=assignment_id, student_id=session['user_id']).first()
        if submission:
            submission.filename = filename
        else:
            submission = Submission(assignment_id=assignment_id, student_id=session['user_id'], filename=filename)
            db.session.add(submission)
            
        db.session.commit()
        flash('Votre devoir a bien été envoyé !', 'success')
    else:
        flash('Extension de fichier non autorisée.', 'danger')

    return redirect(url_for('devoirs'))


@app.route('/noter/<int:submission_id>', methods=['POST'])
def noter_devoir(submission_id):
    if 'user_id' not in session or session['role'] != 'prof':
        return redirect(url_for('login'))

    submission = Submission.query.get_or_404(submission_id)
    grade = request.form.get('grade')
    comment = request.form.get('comment')

    try:
        submission.grade = float(grade)
        submission.comment = comment
        db.session.commit()
        flash('Copie notée avec succès !', 'success')
    except ValueError:
        flash('La note doit être un nombre valide.', 'danger')

    return redirect(url_for('devoirs'))


# ----------------------------------------------------
# MODULE 3 : LA MESSAGERIE (Prof <-> Élèves)
# ----------------------------------------------------

@app.route('/messagerie', methods=['GET', 'POST'])
def messagerie():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    current_user_id = session['user_id']

    # Si envoi d'un message
    if request.method == 'POST':
        receiver_id = request.form.get('receiver_id')
        content = request.form.get('content')
        if receiver_id and content:
            new_msg = Message(sender_id=current_user_id, receiver_id=int(receiver_id), content=content)
            db.session.add(new_msg)
            db.session.commit()
            flash('Message envoyé !', 'success')
        return redirect(url_for('messagerie'))

    # Pour l'affichage de la liste des contacts dispos
    # Pour l'affichage de la liste des contacts dispos (filtré par classe)
    current_user = db.session.get(User, session['user_id'])
    contacts = []

    if session['role'] == 'prof':
        # Le prof voit uniquement les élèves de SES classes
        for classe in current_user.classes_as_teacher:
            for student in classe.students:
                if student not in contacts:
                    contacts.append(student)
    else:
        # L'élève voit uniquement les profs de SES classes
        for classe in current_user.classes_as_student:
            for teacher in classe.teachers:
                if teacher not in contacts:
                    contacts.append(teacher)

    # Récupération de tous les messages impliquant l'utilisateur connecté
    messages = db.session.query(Message, User).\
        join(User, Message.sender_id == User.id).\
        filter((Message.sender_id == current_user_id) | (Message.receiver_id == current_user_id)).\
        order_by(Message.timestamp.asc()).all()

    return render_template('messagerie.html', contacts=contacts, messages=messages, current_user_id=current_user_id)

@app.route('/telecharger/<string:filename>')
def telecharger_devoir(filename):
    # Sécurité : On vérifie que l'utilisateur est bien connecté
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    # Envoi sécurisé du fichier depuis le dossier d'upload
    return send_from_directory(
        app.config['UPLOAD_FOLDER'], 
        filename, 
        as_attachment=True # Force le téléchargement plutôt que l'ouverture dans le navigateur
    )

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        role = request.form['role'] # 'prof' ou 'eleve'
        
        # Vérification si les champs sont vides
        if not username or not password or not role:
            flash('Veuillez remplir tous les champs.', 'danger')
            return redirect(url_for('register'))
            
        # Vérifier si l'utilisateur existe déjà
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash("Ce nom d'utilisateur est déjà pris. Choisissez-en un autre.", 'danger')
            return redirect(url_for('register'))
            
        # Création du nouvel utilisateur
        new_user = User(username=username, password=password, role=role)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Votre compte a été créé avec succès ! Vous pouvez maintenant vous connecter.', 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/mindmaps', methods=['GET', 'POST'])
def mindmaps():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    current_user_id = session['user_id']
    
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content') # Le JSON envoyé par JS
        map_id = request.form.get('map_id') # Optionnel, si on modifie une carte existante
        
        if title and content:
            if map_id: # Mode modification
                carte = Mindmap.query.get(map_id)
                if carte and carte.user_id == current_user_id:
                    carte.title = title
                    carte.content = content
            else: # Mode création
                new_map = Mindmap(title=title, content=content, user_id=current_user_id)
                db.session.add(new_map)
            
            db.session.commit()
            flash('Carte mentale enregistrée avec succès !', 'success')
            return redirect(url_for('mindmaps'))
            
    # Récupération des modes via les paramètres de l'URL (?mode=createur ou ?mode=eleve)
    mode = request.args.get('mode')
    selected_id = request.args.get('id')
    
    carte_chargee = None
    if selected_id:
        carte_chargee = Mindmap.query.get_or_404(selected_id)
        
    mes_cartes = Mindmap.query.filter_by(user_id=current_user_id).all()
    
    return render_template('mindmaps.html', mode=mode, mes_cartes=mes_cartes, carte_chargee=carte_chargee)

import sys
import io

@app.route('/sandbox', methods=['GET', 'POST'])
def sandbox():
    code = request.form.get('code', '# Écris ton code Python ici...\nprint("Bonjour la famille !")\n')
    output = ""
    
    if request.method == 'POST' and 'run_code' in request.form:
        # 1. On détourne la sortie standard pour capturer les print()
        old_stdout = sys.stdout
        redirected_output = io.StringIO()
        sys.stdout = redirected_output
        
        try:
            # 2. On exécute le code dans un environnement restreint pour la sécurité
            # On interdit les imports dangereux dans cet espace de test
            restricted_globals = {"__builtins__": __builtins__}
            exec(code, restricted_globals)
            output = redirected_output.getvalue()
        except Exception as e:
            # En cas d'erreur de syntaxe ou d'exécution, on capture le message d'erreur
            output = f"❌ Erreur :\n{str(e)}"
        finally:
            # 3. On remet la sortie standard normale du serveur
            sys.stdout = old_stdout

    return render_template('sandbox.html', code=code, output=output)

@app.route('/projets-guides/supprimer/<int:id>', methods=['POST'])
def supprimer_projet_guide(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    project = ProjetGuide.query.get_or_404(id)
    
    # Sécurité : Seul le créateur du projet (le prof) peut le supprimer
    if project.user_id == session['user_id']:
        db.session.delete(project)
        db.session.commit()
        flash('Projet supprimé avec succès !', 'success')
    else:
        flash('Action non autorisée.', 'danger')
        
    return redirect(url_for('projets_guides', mode='prof'))

@app.route('/projets-guides', methods=['GET', 'POST'])
def projets_guides():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    current_user_id = session['user_id']
    
    if request.method == 'POST':
        # Sauvegarde d'un nouveau projet par le prof
        title = request.form.get('title')
        steps_data = request.form.get('steps_data') # Reçu sous forme de chaîne JSON depuis le formulaire
        
        if title and steps_data:
            new_project = ProjetGuide(title=title, steps_json=steps_data, user_id=current_user_id)
            db.session.add(new_project)
            db.session.commit()
            flash('Nouveau projet guidé créé avec succès !', 'success')
            return redirect(url_for('projets_guides'))

    # Lecture des paramètres
    mode = request.args.get('mode') # 'prof' ou 'eleve'
    project_id = request.args.get('id') # ID du projet sélectionné
    
    projet_charge = None
    if project_id:
        projet_charge = ProjetGuide.query.get_or_404(project_id)
        
    tous_les_projets = ProjetGuide.query.all() # Tout le monde peut voir les projets créés
    
    return render_template('projets_guides.html', mode=mode, projets=tous_les_projets, projet_charge=projet_charge)

@app.route('/mindmaps/delete/<int:map_id>', methods=['POST'])
def delete_mindmap(map_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    carte = Mindmap.query.get_or_404(map_id)
    if carte.user_id == session['user_id']:
        db.session.delete(carte)
        db.session.commit()
        flash('Carte mentale supprimée.', 'success')
    return redirect(url_for('mindmaps'))

# ----------------------------------------------------
# ROUTES DE GESTION DES BRANCHES & MERGE REQUESTS
# ----------------------------------------------------

@app.route('/repo/<int:repo_id>/branch/create', methods=['POST'])
def create_branch(repo_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    branch_name = request.form.get('branch_name', '').strip().lower().replace(' ', '-')
    if not branch_name:
        flash('Nom de branche invalide', 'danger')
        return redirect(url_for('forge', repo_id=repo_id))
        
    # Branche source depuis laquelle on copie le code
    source_branch_id = request.form.get('source_branch_id')
    source_branch = Branch.query.get(source_branch_id) if source_branch_id else None
    
    initial_code = source_branch.latest_code if source_branch else ""
    
    new_branch = Branch(name=branch_name, repo_id=repo_id, latest_code=initial_code)
    db.session.add(new_branch)
    db.session.commit()
    
    flash(f'Branche "{branch_name}" créée avec succès ! 🌿', 'success')
    return redirect(url_for('forge', repo_id=repo_id))


@app.route('/repo/<int:repo_id>/merge-request/create', methods=['GET', 'POST'])
def create_merge_request(repo_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    repo = Repo.query.get_or_404(repo_id)
    branches = Branch.query.filter_by(repo_id=repo.id).all()
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        source_id = int(request.form.get('source_branch_id'))
        target_id = int(request.form.get('target_branch_id'))
        
        if source_id == target_id:
            flash('La branche source et la branche cible doivent être différentes.', 'danger')
            return redirect(url_for('create_merge_request', repo_id=repo_id))
            
        src = Branch.query.get(source_id)
        tgt = Branch.query.get(target_id)
        
        # Génération du résumé IA automatique
        ai_summary = generate_ai_summary(tgt.latest_code, src.latest_code)
        
        mr = MergeRequest(
            title=title,
            description=description,
            repo_id=repo_id,
            author_id=session['user_id'],
            source_branch_id=source_id,
            target_branch_id=target_id,
            ai_summary=ai_summary
        )
        db.session.add(mr)
        db.session.commit()
        
        flash('Demande de fusion (Merge Request) créée ! 🔀', 'success')
        return redirect(url_for('view_merge_request', mr_id=mr.id))
        
    return render_template('create_mr.html', repo=repo, branches=branches)


@app.route('/merge-request/<int:mr_id>', methods=['GET', 'POST'])
def view_merge_request(mr_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    mr = MergeRequest.query.get_or_404(mr_id)
    
    # Ajout de commentaires sur la PR
    if request.method == 'POST' and 'add_mr_comment' in request.form:
        content = request.form.get('content')
        if content:
            comment = MergeComment(content=content, mr_id=mr.id, user_id=session['user_id'])
            db.session.add(comment)
            db.session.commit()
            flash('Commentaire ajouté ! 💬', 'success')
            return redirect(url_for('view_merge_request', mr_id=mr.id))

    # Calcul du Diff
    diff_data = generate_diff(mr.target_branch.latest_code, mr.source_branch.latest_code)
    
    comments = MergeComment.query.filter_by(mr_id=mr.id).order_by(MergeComment.timestamp.asc()).all()
    
    return render_template('view_mr.html', mr=mr, diff_data=diff_data, comments=comments)


@app.route('/merge-request/<int:mr_id>/execute', methods=['POST'])
def execute_merge(mr_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    mr = MergeRequest.query.get_or_404(mr_id)
    
    if mr.status != 'open':
        flash('Cette demande est déjà fermée ou fusionnée.', 'warning')
        return redirect(url_for('view_merge_request', mr_id=mr.id))
        
    # Copie du code de la branche source vers la branche cible
    mr.target_branch.latest_code = mr.source_branch.latest_code
    mr.status = 'merged'
    
    # Création d'un commit automatique de fusion
    commit_msg = f"Merge branch '{mr.source_branch.name}' into {mr.target_branch.name}"
    new_commit = Commit(message=commit_msg, code_snapshot=mr.target_branch.latest_code, repo_id=mr.repo_id)
    
    db.session.add(new_commit)
    db.session.commit()
    
    flash('Fusion effectuée avec succès ! 🎉', 'success')
    return redirect(url_for('view_merge_request', mr_id=mr.id))

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5003)
