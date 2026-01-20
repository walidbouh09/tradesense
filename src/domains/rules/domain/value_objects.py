"""Rules engine value objects."""

from abc import ABC, abstractmethod
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from ....shared.exceptions.base import ValidationError
from ....shared.kernel.value_object import ValueObject
from ....shared.utils.money import Money


class RuleType(Enum):
    """Rule type enumeration."""
    
    # Loss/Drawdown Rules
    MAX_DAILY_DRAWDOWN = "MAX_DAILY_DRAWDOWN"
    MAX_TOTAL_DRAWDOWN = "MAX_TOTAL_DRAWDOWN"
    MAX_DAILY_LOSS = "MAX_DAILY_LOSS"
    MAX_TOTAL_LOSS = "MAX_TOTAL_LOSS"
    
    # Profit Rules
    PROFIT_TARGET = "PROFIT_TARGET"
    MIN_PROFIT_TARGET = "MIN_PROFIT_TARGET"
    CONSISTENCY_RULE = "CONSISTENCY_RULE"
    
    # Trading Activity Rules
    MAX_TRADES_PER_DAY = "MAX_TRADES_PER_DAY"
    MIN_TRADING_DAYS = "MIN_TRADING_DAYS"
    MAX_POSITION_SIZE = "MAX_POSITION_SIZE"
    MAX_LEVERAGE = "MAX_LEVERAGE"
    
    # Time Rules
    MAX_CHALLENGE_DURATION = "MAX_CHALLENGE_DURATION"
    TRADING_HOURS_RESTRICTION = "TRADING_HOURS_RESTRICTION"
    
    # Instrument Rules
    ALLOWED_INSTRUMENTS = "ALLOWED_INSTRUMENTS"
    FORBIDDEN_INSTRUMENTS = "FORBIDDEN_INSTRUMENTS"
    
    # Strategy Rules
    FORBIDDEN_STRATEGIES = "FORBIDDEN_STRATEGIES"
    MAX_CORRELATION_EXPOSURE = "MAX_CORRELATION_EXPOSURE"


class RuleSeverity(Enum):
    """Rule violation severity levels."""
    
    INFO = "INFO"           # Informational only
    WARNING = "WARNING"     # Warning but not blocking
    VIOLATION = "VIOLATION" # Rule violation but not critical
    CRITICAL = "CRITICAL"   # Critical violation - immediate action required
    FATAL = "FATAL"         # Fatal violation - challenge termination


class RuleOperator(Enum):
    """Rule comparison operators."""
    
    EQUALS = "EQUALS"                    # ==
    NOT_EQUALS = "NOT_EQUALS"           # !=
    GREATER_THAN = "GREATER_THAN"       # >
    GREATER_THAN_OR_EQUAL = "GTE"      # >=
    LESS_THAN = "LESS_THAN"            # <
    LESS_THAN_OR_EQUAL = "LTE"         # <=
    BETWEEN = "BETWEEN"                 # value between min and max
    NOT_BETWEEN = "NOT_BETWEEN"        # value not between min and max
    IN = "IN"                          # value in list
    NOT_IN = "NOT_IN"                  # value not in list
    CONTAINS = "CONTAINS"              # string/list contains value
    NOT_CONTAINS = "NOT_CONTAINS"      # string/list does not contain value


class RuleCondition(ValueObject):
    """Rule condition definition."""
    
    def __init__(
        self,
        field: str,
        operator: RuleOperator,
        value: Any,
        secondary_value: Optional[Any] = None,  # For BETWEEN operations
    ):
        if not field or not field.strip():
            raise ValidationError("Rule condition field cannot be empty")
        
        self.field = field.strip()
        self.operator = operator
        self.value = value
        self.secondary_value = secondary_value
        
        # Validate operator-specific requirements
        if operator in [RuleOperator.BETWEEN, RuleOperator.NOT_BETWEEN]:
            if secondary_value is None:
                raise ValidationError(f"Operator {operator.value} requires secondary_value")
    
    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluate condition against context data."""
        if self.field not in context:
            return False
        
        field_value = context[self.field]
        
        try:
            if self.operator == RuleOperator.EQUALS:
                return field_value == self.value
            elif self.operator == RuleOperator.NOT_EQUALS:
                return field_value != self.value
            elif self.operator == RuleOperator.GREATER_THAN:
                return field_value > self.value
            elif self.operator == RuleOperator.GREATER_THAN_OR_EQUAL:
                return field_value >= self.value
            elif self.operator == RuleOperator.LESS_THAN:
                return field_value < self.value
            elif self.operator == RuleOperator.LESS_THAN_OR_EQUAL:
                return field_value <= self.value
            elif self.operator == RuleOperator.BETWEEN:
                return self.value <= field_value <= self.secondary_value
            elif self.operator == RuleOperator.NOT_BETWEEN:
                return not (self.value <= field_value <= self.secondary_value)
            elif self.operator == RuleOperator.IN:
                return field_value in self.value
            elif self.operator == RuleOperator.NOT_IN:
                return field_value not in self.value
            elif self.operator == RuleOperator.CONTAINS:
                return self.value in field_value
            elif self.operator == RuleOperator.NOT_CONTAINS:
                return self.value not in field_value
            else:
                return False
        except (TypeError, ValueError):
            return False
    
    def explain(self, context: Dict[str, Any]) -> str:
        """Explain condition evaluation for audit purposes."""
        field_value = context.get(self.field, "MISSING")
        result = self.evaluate(context)
        
        operator_text = {
            RuleOperator.EQUALS: "equals",
            RuleOperator.NOT_EQUALS: "does not equal",
            RuleOperator.GREATER_THAN: "is greater than",
            RuleOperator.GREATER_THAN_OR_EQUAL: "is greater than or equal to",
            RuleOperator.LESS_THAN: "is less than",
            RuleOperator.LESS_THAN_OR_EQUAL: "is less than or equal to",
            RuleOperator.BETWEEN: "is between",
            RuleOperator.NOT_BETWEEN: "is not between",
            RuleOperator.IN: "is in",
            RuleOperator.NOT_IN: "is not in",
            RuleOperator.CONTAINS: "contains",
            RuleOperator.NOT_CONTAINS: "does not contain",
        }
        
        op_text = operator_text.get(self.operator, str(self.operator.value))
        
        if self.operator in [RuleOperator.BETWEEN, RuleOperator.NOT_BETWEEN]:
            value_text = f"{self.value} and {self.secondary_value}"
        else:
            value_text = str(self.value)
        
        return f"{self.field} ({field_value}) {op_text} {value_text} = {result}"


class RuleParameter(ValueObject):
    """Rule parameter definition."""
    
    def __init__(
        self,
        name: str,
        value: Any,
        data_type: str,
        description: Optional[str] = None,
    ):
        if not name or not name.strip():
            raise ValidationError("Rule parameter name cannot be empty")
        
        self.name = name.strip()
        self.value = value
        self.data_type = data_type
        self.description = description or ""
        
        # Validate data type
        self._validate_data_type()
    
    def _validate_data_type(self) -> None:
        """Validate parameter value matches declared data type."""
        type_validators = {
            "string": lambda x: isinstance(x, str),
            "integer": lambda x: isinstance(x, int),
            "decimal": lambda x: isinstance(x, (int, float, Decimal)),
            "boolean": lambda x: isinstance(x, bool),
            "money": lambda x: isinstance(x, Money),
            "list": lambda x: isinstance(x, list),
            "dict": lambda x: isinstance(x, dict),
        }
        
        validator = type_validators.get(self.data_type.lower())
        if validator and not validator(self.value):
            raise ValidationError(
                f"Parameter {self.name} value {self.value} does not match type {self.data_type}"
            )


class RuleDefinition(ValueObject):
    """Complete rule definition with metadata."""
    
    def __init__(
        self,
        rule_id: str,
        name: str,
        description: str,
        rule_type: RuleType,
        severity: RuleSeverity,
        conditions: List[RuleCondition],
        parameters: List[RuleParameter],
        enabled: bool = True,
        tags: Optional[List[str]] = None,
        version: str = "1.0",
    ):
        if not rule_id or not rule_id.strip():
            raise ValidationError("Rule ID cannot be empty")
        
        if not name or not name.strip():
            raise ValidationError("Rule name cannot be empty")
        
        if not conditions:
            raise ValidationError("Rule must have at least one condition")
        
        self.rule_id = rule_id.strip()
        self.name = name.strip()
        self.description = description.strip()
        self.rule_type = rule_type
        self.severity = severity
        self.conditions = conditions
        self.parameters = parameters
        self.enabled = enabled
        self.tags = tags or []
        self.version = version
    
    def get_parameter_value(self, parameter_name: str) -> Any:
        """Get parameter value by name."""
        for param in self.parameters:
            if param.name == parameter_name:
                return param.value
        return None
    
    def has_tag(self, tag: str) -> bool:
        """Check if rule has specific tag."""
        return tag in self.tags


class RuleEvaluationResult(ValueObject):
    """Result of rule evaluation."""
    
    def __init__(
        self,
        rule_id: str,
        rule_name: str,
        passed: bool,
        severity: RuleSeverity,
        message: str,
        details: Dict[str, Any],
        condition_results: List[str],
        evaluation_timestamp: str,
        context_snapshot: Dict[str, Any],
    ):
        self.rule_id = rule_id
        self.rule_name = rule_name
        self.passed = passed
        self.severity = severity
        self.message = message
        self.details = details
        self.condition_results = condition_results
        self.evaluation_timestamp = evaluation_timestamp
        self.context_snapshot = context_snapshot
    
    @property
    def is_violation(self) -> bool:
        """Check if result represents a rule violation."""
        return not self.passed
    
    @property
    def is_critical(self) -> bool:
        """Check if violation is critical."""
        return not self.passed and self.severity in [RuleSeverity.CRITICAL, RuleSeverity.FATAL]
    
    @property
    def requires_action(self) -> bool:
        """Check if violation requires immediate action."""
        return not self.passed and self.severity in [RuleSeverity.VIOLATION, RuleSeverity.CRITICAL, RuleSeverity.FATAL]


class RuleSet(ValueObject):
    """Collection of rules for a specific context."""
    
    def __init__(
        self,
        name: str,
        description: str,
        rules: List[RuleDefinition],
        tags: Optional[List[str]] = None,
        version: str = "1.0",
    ):
        if not name or not name.strip():
            raise ValidationError("Rule set name cannot be empty")
        
        self.name = name.strip()
        self.description = description.strip()
        self.rules = rules
        self.tags = tags or []
        self.version = version
    
    def get_rules_by_type(self, rule_type: RuleType) -> List[RuleDefinition]:
        """Get all rules of specific type."""
        return [rule for rule in self.rules if rule.rule_type == rule_type]
    
    def get_rules_by_severity(self, severity: RuleSeverity) -> List[RuleDefinition]:
        """Get all rules of specific severity."""
        return [rule for rule in self.rules if rule.severity == severity]
    
    def get_enabled_rules(self) -> List[RuleDefinition]:
        """Get all enabled rules."""
        return [rule for rule in self.rules if rule.enabled]
    
    def get_rules_by_tag(self, tag: str) -> List[RuleDefinition]:
        """Get all rules with specific tag."""
        return [rule for rule in self.rules if rule.has_tag(tag)]


# Pre-defined Rule Templates
class RuleTemplates:
    """Pre-defined rule templates for common prop firm rules."""
    
    @staticmethod
    def max_daily_drawdown(max_drawdown_percent: Decimal) -> RuleDefinition:
        """Create max daily drawdown rule."""
        return RuleDefinition(
            rule_id="MAX_DAILY_DRAWDOWN",
            name="Maximum Daily Drawdown",
            description=f"Daily drawdown cannot exceed {max_drawdown_percent}% of account balance",
            rule_type=RuleType.MAX_DAILY_DRAWDOWN,
            severity=RuleSeverity.FATAL,
            conditions=[
                RuleCondition(
                    field="daily_drawdown_percent",
                    operator=RuleOperator.LESS_THAN_OR_EQUAL,
                    value=max_drawdown_percent,
                )
            ],
            parameters=[
                RuleParameter("max_drawdown_percent", max_drawdown_percent, "decimal"),
            ],
            tags=["drawdown", "risk", "daily"],
        )
    
    @staticmethod
    def max_total_drawdown(max_drawdown_percent: Decimal) -> RuleDefinition:
        """Create max total drawdown rule."""
        return RuleDefinition(
            rule_id="MAX_TOTAL_DRAWDOWN",
            name="Maximum Total Drawdown",
            description=f"Total drawdown cannot exceed {max_drawdown_percent}% of initial balance",
            rule_type=RuleType.MAX_TOTAL_DRAWDOWN,
            severity=RuleSeverity.FATAL,
            conditions=[
                RuleCondition(
                    field="total_drawdown_percent",
                    operator=RuleOperator.LESS_THAN_OR_EQUAL,
                    value=max_drawdown_percent,
                )
            ],
            parameters=[
                RuleParameter("max_drawdown_percent", max_drawdown_percent, "decimal"),
            ],
            tags=["drawdown", "risk", "total"],
        )
    
    @staticmethod
    def profit_target(target_amount: Money) -> RuleDefinition:
        """Create profit target rule."""
        return RuleDefinition(
            rule_id="PROFIT_TARGET",
            name="Profit Target",
            description=f"Must achieve profit of {target_amount}",
            rule_type=RuleType.PROFIT_TARGET,
            severity=RuleSeverity.INFO,
            conditions=[
                RuleCondition(
                    field="total_profit",
                    operator=RuleOperator.GREATER_THAN_OR_EQUAL,
                    value=target_amount.amount,
                )
            ],
            parameters=[
                RuleParameter("target_amount", target_amount, "money"),
            ],
            tags=["profit", "target", "completion"],
        )
    
    @staticmethod
    def max_trades_per_day(max_trades: int) -> RuleDefinition:
        """Create max trades per day rule."""
        return RuleDefinition(
            rule_id="MAX_TRADES_PER_DAY",
            name="Maximum Trades Per Day",
            description=f"Cannot exceed {max_trades} trades per day",
            rule_type=RuleType.MAX_TRADES_PER_DAY,
            severity=RuleSeverity.VIOLATION,
            conditions=[
                RuleCondition(
                    field="daily_trade_count",
                    operator=RuleOperator.LESS_THAN_OR_EQUAL,
                    value=max_trades,
                )
            ],
            parameters=[
                RuleParameter("max_trades", max_trades, "integer"),
            ],
            tags=["trading", "activity", "daily"],
        )
    
    @staticmethod
    def consistency_rule(max_single_day_percent: Decimal) -> RuleDefinition:
        """Create consistency rule (max profit from single day)."""
        return RuleDefinition(
            rule_id="CONSISTENCY_RULE",
            name="Consistency Rule",
            description=f"No single day can contribute more than {max_single_day_percent}% of total profit",
            rule_type=RuleType.CONSISTENCY_RULE,
            severity=RuleSeverity.CRITICAL,
            conditions=[
                RuleCondition(
                    field="max_single_day_profit_percent",
                    operator=RuleOperator.LESS_THAN_OR_EQUAL,
                    value=max_single_day_percent,
                )
            ],
            parameters=[
                RuleParameter("max_single_day_percent", max_single_day_percent, "decimal"),
            ],
            tags=["consistency", "profit", "risk"],
        )
    
    @staticmethod
    def min_trading_days(min_days: int) -> RuleDefinition:
        """Create minimum trading days rule."""
        return RuleDefinition(
            rule_id="MIN_TRADING_DAYS",
            name="Minimum Trading Days",
            description=f"Must trade for at least {min_days} days",
            rule_type=RuleType.MIN_TRADING_DAYS,
            severity=RuleSeverity.VIOLATION,
            conditions=[
                RuleCondition(
                    field="trading_days",
                    operator=RuleOperator.GREATER_THAN_OR_EQUAL,
                    value=min_days,
                )
            ],
            parameters=[
                RuleParameter("min_days", min_days, "integer"),
            ],
            tags=["trading", "activity", "minimum"],
        )