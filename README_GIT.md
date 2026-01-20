# 🚀 Guide Git - TradeSense AI

## Initialisation du dépôt Git

### 1. Initialiser Git (si pas déjà fait)

```bash
git init
```

### 2. Ajouter le remote (votre dépôt GitHub/GitLab)

```bash
# GitHub
git remote add origin https://github.com/votre-username/tradesense.git

# Ou GitLab
git remote add origin https://gitlab.com/votre-username/tradesense.git

# Ou SSH
git remote add origin git@github.com:votre-username/tradesense.git
```

### 3. Vérifier les fichiers à commiter

```bash
# Voir le statut
git status

# Voir les fichiers ignorés
git status --ignored
```

### 4. Ajouter les fichiers

```bash
# Ajouter tous les fichiers (sauf ceux dans .gitignore)
git add .

# Ou ajouter des fichiers spécifiques
git add app/ frontend/ docker-compose.yml Dockerfile.* requirements.txt
```

### 5. Créer le premier commit

```bash
git commit -m "Initial commit: TradeSense AI - Flask + React Trading Platform"
```

### 6. Pousser vers le dépôt distant

```bash
# Première fois (créer la branche main)
git branch -M main
git push -u origin main

# Pushs suivants
git push
```

## 📋 Checklist avant de pusher

### ✅ Fichiers sensibles protégés

Vérifiez que ces fichiers sont dans `.gitignore`:
- [ ] `.env` (contient les secrets)
- [ ] `logs/` (fichiers de logs)
- [ ] `*.db` (bases de données locales)
- [ ] `node_modules/` (dépendances Node)
- [ ] `__pycache__/` (cache Python)
- [ ] `.vscode/` (configuration IDE)

### ✅ Fichiers à inclure

Ces fichiers DOIVENT être dans le dépôt:
- [x] `.env.example` (template sans secrets)
- [x] `.gitignore`
- [x] `README.md`
- [x] `docker-compose.yml`
- [x] `Dockerfile.backend`
- [x] `Dockerfile.frontend`
- [x] `requirements.txt`
- [x] `package.json`
- [x] Code source (`app/`, `frontend/src/`)

### ✅ Vérification de sécurité

```bash
# Vérifier qu'aucun secret n'est commité
git diff --cached | grep -i "password\|secret\|key"

# Si des secrets sont trouvés, les retirer:
git reset HEAD fichier-avec-secret
```

## 🔄 Workflow Git recommandé

### Développement quotidien

```bash
# 1. Créer une branche pour une nouvelle fonctionnalité
git checkout -b feature/nom-de-la-feature

# 2. Faire vos modifications
# ... coder ...

# 3. Voir les changements
git status
git diff

# 4. Ajouter et commiter
git add .
git commit -m "feat: description de la fonctionnalité"

# 5. Pousser la branche
git push -u origin feature/nom-de-la-feature

# 6. Créer une Pull Request sur GitHub/GitLab

# 7. Après merge, revenir sur main
git checkout main
git pull origin main
```

### Types de commits (Convention)

```bash
# Nouvelle fonctionnalité
git commit -m "feat: ajout de l'authentification JWT"

# Correction de bug
git commit -m "fix: correction du hot reload Docker"

# Documentation
git commit -m "docs: mise à jour du README"

# Refactoring
git commit -m "refactor: restructuration des API endpoints"

# Style/Format
git commit -m "style: formatage du code avec Black"

# Tests
git commit -m "test: ajout des tests pour market_data"

# Configuration
git commit -m "chore: mise à jour des dépendances"
```

## 🔐 Sécurité Git

### Supprimer un fichier sensible déjà commité

```bash
# Supprimer du dépôt mais garder localement
git rm --cached .env

# Ajouter à .gitignore
echo ".env" >> .gitignore

# Commiter
git commit -m "chore: remove .env from repository"
git push
```

### Nettoyer l'historique (si secrets exposés)

```bash
# ATTENTION: Réécrit l'historique!
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch .env" \
  --prune-empty --tag-name-filter cat -- --all

# Force push (dangereux!)
git push origin --force --all
```

## 📦 Créer une release

```bash
# Créer un tag
git tag -a v1.0.0 -m "Release version 1.0.0"

# Pousser le tag
git push origin v1.0.0

# Ou pousser tous les tags
git push origin --tags
```

## 🌿 Gestion des branches

```bash
# Lister les branches
git branch -a

# Créer une branche
git checkout -b develop

# Changer de branche
git checkout main

# Supprimer une branche locale
git branch -d feature/old-feature

# Supprimer une branche distante
git push origin --delete feature/old-feature

# Mettre à jour depuis main
git checkout feature/ma-feature
git merge main
```

## 🔄 Synchronisation

```bash
# Récupérer les changements
git fetch origin

# Récupérer et merger
git pull origin main

# Voir les différences avec le remote
git diff main origin/main
```

## 📝 Commandes utiles

```bash
# Voir l'historique
git log --oneline --graph --all

# Voir les fichiers modifiés
git diff --name-only

# Annuler les modifications locales
git checkout -- fichier.py

# Annuler le dernier commit (garder les changements)
git reset --soft HEAD~1

# Annuler le dernier commit (supprimer les changements)
git reset --hard HEAD~1

# Voir qui a modifié une ligne
git blame fichier.py

# Rechercher dans l'historique
git log --all --grep="mot-clé"
```

## 🚨 En cas de problème

### Conflit de merge

```bash
# 1. Voir les fichiers en conflit
git status

# 2. Éditer les fichiers et résoudre les conflits
# Chercher les marqueurs: <<<<<<<, =======, >>>>>>>

# 3. Marquer comme résolu
git add fichier-resolu.py

# 4. Finaliser le merge
git commit
```

### Récupérer un fichier supprimé

```bash
# Trouver le commit où le fichier existait
git log -- fichier-supprime.py

# Restaurer depuis un commit
git checkout <commit-hash> -- fichier-supprime.py
```

## 📚 Ressources

- [Git Documentation](https://git-scm.com/doc)
- [GitHub Guides](https://guides.github.com/)
- [Conventional Commits](https://www.conventionalcommits.org/)

## ✅ Commandes pour pousser maintenant

```bash
# Vérifier le statut
git status

# Ajouter tous les fichiers
git add .

# Commiter
git commit -m "feat: TradeSense AI - Complete trading platform with Docker hot reload"

# Pousser
git push -u origin main
```

Votre projet est maintenant prêt à être poussé sur Git! 🎉
