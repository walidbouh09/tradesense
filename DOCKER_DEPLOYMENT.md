# 🐳 TradeSense AI - Docker Deployment Guide

## Architecture Professionnelle

```
┌─────────────────────────────────────────────────────────────┐
│                         Nginx (Port 80)                      │
│                    Reverse Proxy & Load Balancer             │
└────────────┬────────────────────────────┬───────────────────┘
             │                            │
             ▼                            ▼
┌────────────────────────┐    ┌──────────────────────────┐
│   Frontend (Port 3000) │    │  Backend API (Port 5000) │
│   React + Nginx        │    │  Flask + Gunicorn        │
└────────────────────────┘    └──────────┬───────────────┘
                                         │
                    ┌────────────────────┼────────────────────┐
                    ▼                    ▼                    ▼
         ┌──────────────────┐ ┌─────────────────┐ ┌──────────────────┐
         │ PostgreSQL       │ │ Redis Cache     │ │ Celery Workers   │
         │ (Port 5432)      │ │ (Port 6379)     │ │ Background Tasks │
         └──────────────────┘ └─────────────────┘ └──────────────────┘
```

## 🚀 Démarrage Rapide

### Prérequis
- Docker 20.10+
- Docker Compose 2.0+
- 4GB RAM minimum
- 10GB espace disque

### 1. Cloner et Configurer

```bash
# Cloner le projet
cd tradesense

# Copier et configurer l'environnement
cp .env.production .env
# Éditer .env avec vos valeurs de production

# Générer des clés secrètes
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 2. Construire les Images

```bash
# Construire toutes les images
docker-compose build

# Ou construire individuellement
docker-compose build backend
docker-compose build frontend
```

### 3. Démarrer les Services

```bash
# Démarrer tous les services
docker-compose up -d

# Vérifier le statut
docker-compose ps

# Voir les logs
docker-compose logs -f
```

### 4. Accéder à l'Application

```
Frontend:  http://localhost:3000
Backend:   http://localhost:5000
Nginx:     http://localhost:80
```

## 📊 Services Disponibles

### Frontend (React)
- **Port**: 3000
- **URL**: http://localhost:3000
- **Technologie**: React 18 + Nginx
- **Features**:
  - Dashboard interactif
  - Gestion des challenges
  - Monitoring en temps réel
  - Design responsive

### Backend (Flask)
- **Port**: 5000
- **URL**: http://localhost:5000
- **Technologie**: Flask + Gunicorn
- **Workers**: 4 workers, 2 threads each
- **Features**:
  - API RESTful
  - Payment simulation
  - Access control
  - Morocco market integration

### PostgreSQL
- **Port**: 5432
- **Database**: tradesense
- **User**: tradesense_user
- **Auto-init**: Schema loaded on first start

### Redis
- **Port**: 6379
- **Usage**: Caching, sessions, Celery broker

### Nginx
- **Port**: 80
- **Role**: Reverse proxy, load balancer
- **Features**: Gzip, caching, SSL ready

## 🔧 Commandes Utiles

### Gestion des Services

```bash
# Démarrer
docker-compose up -d

# Arrêter
docker-compose down

# Redémarrer
docker-compose restart

# Arrêter et supprimer les volumes
docker-compose down -v

# Voir les logs
docker-compose logs -f [service]

# Logs d'un service spécifique
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f postgres
```

### Accès aux Conteneurs

```bash
# Shell dans le backend
docker-compose exec backend bash

# Shell dans le frontend
docker-compose exec frontend sh

# Shell dans PostgreSQL
docker-compose exec postgres psql -U tradesense_user -d tradesense

# Shell dans Redis
docker-compose exec redis redis-cli
```

### Base de Données

```bash
# Exécuter une migration
docker-compose exec backend flask db upgrade

# Créer une migration
docker-compose exec backend flask db migrate -m "description"

# Backup de la base
docker-compose exec postgres pg_dump -U tradesense_user tradesense > backup.sql

# Restore de la base
docker-compose exec -T postgres psql -U tradesense_user tradesense < backup.sql
```

### Monitoring

```bash
# Statistiques des conteneurs
docker stats

# Inspecter un conteneur
docker inspect tradesense-backend

# Voir les processus
docker-compose top

# Vérifier la santé
docker-compose ps
```

## 🔍 Health Checks

Tous les services ont des health checks configurés:

```bash
# Backend health
curl http://localhost:5000/health

# Frontend health
curl http://localhost:3000/health

# PostgreSQL health
docker-compose exec postgres pg_isready -U tradesense_user

# Redis health
docker-compose exec redis redis-cli ping
```

## 📈 Scaling

### Scaler le Backend

```bash
# Augmenter à 3 instances
docker-compose up -d --scale backend=3

# Nginx fera automatiquement le load balancing
```

### Scaler les Workers Celery

```bash
# Ajouter des workers
docker-compose up -d --scale celery-worker=4
```

## 🔒 Sécurité

### Variables d'Environnement Sensibles

```bash
# Générer des clés sécurisées
openssl rand -base64 32

# Ou avec Python
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### SSL/TLS (Production)

1. Obtenir des certificats (Let's Encrypt):
```bash
certbot certonly --standalone -d yourdomain.com
```

2. Monter les certificats dans nginx:
```yaml
volumes:
  - /etc/letsencrypt:/etc/nginx/ssl:ro
```

3. Mettre à jour nginx.conf pour HTTPS

## 🐛 Dépannage

### Le frontend ne se connecte pas au backend

```bash
# Vérifier les logs
docker-compose logs backend

# Vérifier le réseau
docker network inspect tradesense_tradesense-network

# Tester la connectivité
docker-compose exec frontend ping backend
```

### Erreur de base de données

```bash
# Vérifier PostgreSQL
docker-compose logs postgres

# Réinitialiser la base
docker-compose down -v
docker-compose up -d postgres
docker-compose exec postgres psql -U tradesense_user -d tradesense -f /docker-entrypoint-initdb.d/01-schema.sql
```

### Problème de cache Redis

```bash
# Vider le cache
docker-compose exec redis redis-cli FLUSHALL

# Redémarrer Redis
docker-compose restart redis
```

### Rebuild complet

```bash
# Tout supprimer et reconstruire
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

## 📊 Monitoring en Production

### Logs Centralisés

```bash
# Tous les logs
docker-compose logs -f --tail=100

# Logs avec timestamps
docker-compose logs -f -t

# Logs d'erreur uniquement
docker-compose logs | grep ERROR
```

### Métriques

```bash
# CPU et mémoire
docker stats --no-stream

# Espace disque
docker system df

# Volumes
docker volume ls
```

## 🚀 Déploiement en Production

### 1. Préparer l'Environnement

```bash
# Créer .env.production avec les vraies valeurs
cp .env.production .env

# Éditer les secrets
nano .env
```

### 2. Construire pour Production

```bash
# Build optimisé
docker-compose -f docker-compose.yml build --no-cache

# Tester localement
docker-compose up -d
```

### 3. Déployer

```bash
# Sur le serveur de production
git pull origin main
docker-compose down
docker-compose build
docker-compose up -d

# Vérifier
docker-compose ps
curl http://localhost/health
```

## 📝 Checklist de Déploiement

- [ ] Variables d'environnement configurées
- [ ] Clés secrètes générées et sécurisées
- [ ] Base de données initialisée
- [ ] Certificats SSL installés (production)
- [ ] Firewall configuré
- [ ] Backups automatiques configurés
- [ ] Monitoring configuré
- [ ] Logs centralisés configurés
- [ ] Health checks fonctionnels
- [ ] Tests de charge effectués

## 🎯 Performance

### Optimisations Appliquées

1. **Frontend**:
   - Build optimisé avec React
   - Gzip compression
   - Cache des assets statiques
   - Code splitting

2. **Backend**:
   - Gunicorn avec 4 workers
   - Connection pooling PostgreSQL
   - Redis caching
   - Async I/O avec eventlet

3. **Database**:
   - Indexes optimisés
   - Connection pooling
   - Query optimization

4. **Nginx**:
   - Gzip compression
   - Static file caching
   - Load balancing
   - Keep-alive connections

## 📚 Documentation Complète

- `README.md` - Vue d'ensemble du projet
- `IMPLEMENTATION_STATUS.md` - État de l'implémentation
- `FINAL_RESULT_SUMMARY.md` - Résumé des fonctionnalités
- `ENV_CONFIGURATION_GUIDE.md` - Guide de configuration

## 🆘 Support

En cas de problème:

1. Vérifier les logs: `docker-compose logs -f`
2. Vérifier la santé: `docker-compose ps`
3. Consulter la documentation
4. Vérifier les issues GitHub

---

**Status**: ✅ Production Ready  
**Version**: 1.0.0  
**Docker Compose**: 3.8  
**Dernière mise à jour**: Janvier 2026
