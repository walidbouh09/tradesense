# Guide de Contribution - TradeSense AI

Merci de votre intérêt pour contribuer à TradeSense AI! 🎉

## 🤝 Comment contribuer

### 1. Fork le projet

Cliquez sur le bouton "Fork" en haut à droite de la page GitHub.

### 2. Clonez votre fork

```bash
git clone https://github.com/votre-username/tradesense.git
cd tradesense
```

### 3. Créez une branche

```bash
git checkout -b feature/ma-nouvelle-fonctionnalite
```

### 4. Faites vos modifications

- Suivez les conventions de code du projet
- Ajoutez des tests si nécessaire
- Mettez à jour la documentation

### 5. Commitez vos changements

```bash
git add .
git commit -m "feat: description de la fonctionnalité"
```

Utilisez les préfixes de commit conventionnels:
- `feat:` - Nouvelle fonctionnalité
- `fix:` - Correction de bug
- `docs:` - Documentation
- `style:` - Formatage
- `refactor:` - Refactoring
- `test:` - Tests
- `chore:` - Maintenance

### 6. Poussez vers votre fork

```bash
git push origin feature/ma-nouvelle-fonctionnalite
```

### 7. Créez une Pull Request

Allez sur GitHub et créez une Pull Request depuis votre branche vers `main`.

## 📋 Standards de code

### Python (Backend)

- Suivez PEP 8
- Utilisez Black pour le formatage
- Ajoutez des docstrings
- Type hints recommandés

```python
def calculate_risk_score(portfolio: Portfolio) -> float:
    """
    Calculate risk score for a portfolio.
    
    Args:
        portfolio: Portfolio object to analyze
        
    Returns:
        Risk score between 0 and 100
    """
    pass
```

### TypeScript/React (Frontend)

- Utilisez TypeScript
- Composants fonctionnels avec hooks
- Props typées
- Commentaires JSDoc

```typescript
interface MarketDataProps {
  symbol: string;
  interval?: string;
}

/**
 * Display real-time market data for a symbol
 */
const MarketData: React.FC<MarketDataProps> = ({ symbol, interval = '1d' }) => {
  // ...
};
```

## 🧪 Tests

### Backend

```bash
# Lancer les tests
pytest

# Avec coverage
pytest --cov=app tests/
```

### Frontend

```bash
cd frontend

# Lancer les tests
npm test

# Avec coverage
npm test -- --coverage
```

## 📝 Documentation

- Mettez à jour le README si nécessaire
- Ajoutez des commentaires pour le code complexe
- Documentez les nouvelles API dans les docstrings
- Mettez à jour les guides si vous changez le workflow

## 🐛 Signaler un bug

Créez une issue avec:
- Description claire du problème
- Étapes pour reproduire
- Comportement attendu vs actuel
- Captures d'écran si applicable
- Environnement (OS, versions, etc.)

## 💡 Proposer une fonctionnalité

Créez une issue avec:
- Description de la fonctionnalité
- Cas d'usage
- Bénéfices attendus
- Implémentation proposée (optionnel)

## ✅ Checklist avant PR

- [ ] Le code suit les standards du projet
- [ ] Les tests passent
- [ ] La documentation est à jour
- [ ] Pas de secrets/credentials dans le code
- [ ] Les commits suivent la convention
- [ ] La PR a une description claire

## 🎯 Domaines de contribution

### Backend
- Nouveaux endpoints API
- Amélioration des algorithmes de risque
- Optimisation des performances
- Intégration de nouvelles sources de données

### Frontend
- Nouveaux composants UI
- Amélioration de l'UX
- Optimisation des performances
- Accessibilité

### Infrastructure
- Amélioration Docker
- CI/CD
- Monitoring
- Sécurité

### Documentation
- Guides utilisateur
- Tutoriels
- Traductions
- Exemples de code

## 📞 Contact

Pour les questions:
- Ouvrez une issue
- Contactez les mainteneurs

Merci de contribuer à TradeSense AI! 🚀
