# Guide de Déploiement TradeSense AI

## 🚀 Démarrage Rapide

### Prérequis
- Docker et Docker Compose installés
- Node.js 18+ (pour développement local)
- Python 3.11+ (pour développement local)

## 📦 Déploiement avec Docker (Recommandé)

### 1. Configuration de l'environnement

Copiez le fichier d'environnement:
```bash
cp .env.example .env
```

Modifiez `.env` selon vos besoins (les valeurs par défaut fonctionnent pour le développement).

### 2. Démarrage des services

```bash
# Démarrer tous les services
docker-compose up --build

# Ou en arrière-plan
docker-compose up -d --build
```

### 3. Accès aux services

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:5000
- **API Health**: http://localhost:5000/api/health
- **Market Data**: http://localhost:5000/api/market/overview

### 4. Arrêt des services

```bash
docker-compose down

# Avec suppression des volumes
docker-compose down -v
```

## 🛠️ Développement Local (Sans Docker)

### Backend

```bash
# Installer les dépendances
pip install -r requirements.txt

# Démarrer le serveur
python start_backend.py
```

### Frontend

```bash
cd frontend

# Installer les dépendances
npm install

# Démarrer le serveur de développement
npm start
```

## 🔧 Configuration

### Variables d'environnement importantes

**Backend (.env)**:
```env
APP_PORT=5000
DATABASE_URL=postgresql://tradesense_user:tradesense_pass@localhost:5432/tradesense
REDIS_URL=redis://localhost:6379/0
CORS_ORIGINS=http://localhost:3000
```

**Frontend (frontend/.env)**:
```env
REACT_APP_API_URL=http://localhost:5000
REACT_APP_WS_URL=ws://localhost:5000
```

## 🐛 Dépannage

### Le frontend ne se connecte pas au backend

1. Vérifiez que le backend est démarré:
   ```bash
   curl http://localhost:5000/api/health
   ```

2. Vérifiez la configuration CORS dans `.env`:
   ```env
   CORS_ORIGINS=http://localhost:3000
   ```

3. Vérifiez l'URL de l'API dans `frontend/.env`:
   ```env
   REACT_APP_API_URL=http://localhost:5000
   ```

### Hot reload ne fonctionne pas

1. Vérifiez que les volumes sont montés dans `docker-compose.yml`
2. Redémarrez le conteneur frontend:
   ```bash
   docker-compose restart frontend
   ```

### Erreurs de build Docker

1. Nettoyez les images et volumes:
   ```bash
   docker-compose down -v
   docker system prune -a
   ```

2. Reconstruisez:
   ```bash
   docker-compose up --build
   ```

## 📊 Endpoints API Disponibles

### Health & Status
- `GET /health` - Health check général
- `GET /api/health` - Health check API

### Market Data
- `GET /api/market/overview` - Vue d'ensemble du marché
- `GET /api/market/status` - Statut des marchés
- `GET /api/market/health` - Santé du service de données
- `GET /api/market/history/:symbol` - Historique d'un symbole
- `GET /api/market/morocco/:symbol` - Actions marocaines

### Challenges
- `GET /api/challenges` - Liste des challenges
- `GET /api/challenges/:id` - Détails d'un challenge
- `POST /api/challenges` - Créer un challenge

### Risk Management
- `GET /api/risk/scores` - Scores de risque
- `GET /api/risk/alerts` - Alertes de risque
- `GET /api/risk/summary` - Résumé des risques

## 🔐 Sécurité

### Pour la production:

1. Changez toutes les clés secrètes dans `.env`:
   ```env
   SECRET_KEY=votre-clé-secrète-forte
   JWT_SECRET_KEY=votre-clé-jwt-forte
   ```

2. Désactivez le mode debug:
   ```env
   FLASK_DEBUG=false
   APP_DEBUG=false
   ```

3. Configurez HTTPS avec Nginx

4. Utilisez des mots de passe forts pour PostgreSQL

## 📝 Notes

- Le système de paiement est en mode SIMULATION (aucun argent réel)
- Les données de marché utilisent Yahoo Finance (gratuit)
- Les actions marocaines utilisent du web scraping respectueux
- Hot reload activé en développement pour React et Flask

## 🆘 Support

Pour les problèmes:
1. Vérifiez les logs: `docker-compose logs -f`
2. Consultez `DOCKER_HOT_RELOAD_GUIDE.md`
3. Consultez `DOCKER_COMMANDS.md`
