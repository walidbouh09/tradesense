"""
Module: challenge_engine

Pure, side-effect free evaluation of a trading challenge status.

Contrainte: aucune dépendance Flask ou base de données — logique pure uniquement.

Fonction principale:
    evaluate_challenge(start_balance, equity, daily_equity, current_status)

Entrées attendues (numériques acceptées sous forme int/float/Decimal/str):
    - start_balance: solde initial du challenge (utilisé aussi comme référence pour le drawdown total)
    - equity: valeur courante de l'équity
    - daily_equity: solde d'ouverture du jour (utilisé pour calcul drawdown journalier)
    - current_status: statut courant (ex: 'PENDING', 'ACTIVE', 'FAILED', 'FUNDED')

Sortie:
    Tuple (new_status: str, reason: Optional[str])

Règles fixes:
    - Perte journalière max: 5%  -> raison 'MAX_DAILY_DRAWDOWN' -> status 'FAILED'
    - Perte totale max: 10%    -> raison 'MAX_TOTAL_DRAWDOWN' -> status 'FAILED'
    - Objectif profit: 10%     -> raison 'PROFIT_TARGET' -> status 'FUNDED'

Remarques/assomptions:
    - La fonction n'a aucun effet de bord et ne modifie aucune donnée externe.
    - Si `current_status` n'est pas 'ACTIVE', la fonction renvoie immédiatement le statut inchangé
      (aucune activation automatique, car l'événement d'activation appartient à l'orchestrateur).
    - Pour le calcul du drawdown total, on utilise `start_balance` comme référence maximale
      disponible (puisqu'aucun `max_equity_ever` n'est fourni).
"""

from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple

# Règles (constants)
DAILY_MAX_DRAWDOWN = Decimal('0.05')   # 5% journalier
TOTAL_MAX_DRAWDOWN = Decimal('0.10')   # 10% total
PROFIT_TARGET = Decimal('0.10')        # 10% profit


def _to_decimal(value) -> Decimal:
    """Convertit une valeur en Decimal de façon sûre.

    Accepte int/float/str/Decimal. En cas d'erreur, lève InvalidOperation.
    """
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise InvalidOperation(f"Cannot convert to Decimal: {value!r}") from exc


def evaluate_challenge(
    start_balance,
    equity,
    daily_equity,
    current_status: str,
) -> Tuple[str, Optional[str]]:
    """
    Évalue l'état d'un challenge de trading en sortie pure.

    Ne provoque aucun effet de bord. Retourne (new_status, reason).

    Logique:
    - Si le statut courant n'est pas 'ACTIVE', on ne prend pas de décision et on renvoie
      le statut inchangé (aucune activation automatique ici).
    - Calculer le drawdown journalier et total ; si l'un dépasse son seuil → 'FAILED'.
    - Si l'objectif de profit est atteint → 'FUNDED'.
    - Sinon rester 'ACTIVE'.
    """
    # Normaliser/valider les valeurs numériques
    try:
        sb = _to_decimal(start_balance)
        eq = _to_decimal(equity)
        de = _to_decimal(daily_equity)
    except InvalidOperation:
        raise

    # Only evaluate when challenge is ACTIVE; otherwise return unchanged status
    if str(current_status).upper() != 'ACTIVE':
        return (current_status, None)

    # Safety: avoid division by zero. If a baseline is non-positive, treat its drawdown as 0.
    # Drawdown journalier: (daily_start - current) / daily_start
    daily_drawdown = Decimal('0')
    if de > 0:
        loss = de - eq
        if loss > 0:
            daily_drawdown = (loss / de)

    if daily_drawdown > DAILY_MAX_DRAWDOWN:
        return ('FAILED', 'MAX_DAILY_DRAWDOWN')

    # Drawdown total: (start_balance - current) / start_balance
    total_drawdown = Decimal('0')
    if sb > 0:
        loss_total = sb - eq
        if loss_total > 0:
            total_drawdown = (loss_total / sb)

    if total_drawdown > TOTAL_MAX_DRAWDOWN:
        return ('FAILED', 'MAX_TOTAL_DRAWDOWN')

    # Profit target: (current - start) / start
    profit_pct = Decimal('0')
    if sb > 0:
        gain = eq - sb
        if gain > 0:
            profit_pct = (gain / sb)

    if profit_pct >= PROFIT_TARGET:
        return ('FUNDED', 'PROFIT_TARGET')

    # No rule triggered -> remain ACTIVE
    return ('ACTIVE', None)


__all__ = [
    'evaluate_challenge',
    'DAILY_MAX_DRAWDOWN',
    'TOTAL_MAX_DRAWDOWN',
    'PROFIT_TARGET',
]
