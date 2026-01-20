"""Trading infrastructure repository implementations."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....shared.exceptions.base import InfrastructureError
from ..domain.entities import Order
from ..domain.repositories import OrderRepository
from ..domain.value_objects import OrderStatus, Symbol
from .models import OrderModel


class SqlAlchemyOrderRepository(OrderRepository):
    """SQLAlchemy implementation of OrderRepository."""
    
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
    
    async def save(self, aggregate: Order) -> None:
        """Save an order aggregate."""
        try:
            # Check if order exists
            stmt = select(OrderModel).where(OrderModel.id == aggregate.id)
            result = await self._session.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if existing:
                # Update existing
                self._update_model_from_aggregate(existing, aggregate)
            else:
                # Create new
                model = self._create_model_from_aggregate(aggregate)
                self._session.add(model)
            
            await self._session.commit()
        except Exception as e:
            await self._session.rollback()
            raise InfrastructureError(f"Failed to save order: {e}") from e
    
    async def get_by_id(self, id: UUID) -> Optional[Order]:
        """Get order by ID."""
        try:
            stmt = select(OrderModel).where(OrderModel.id == id)
            result = await self._session.execute(stmt)
            model = result.scalar_one_or_none()
            
            if not model:
                return None
            
            return self._create_aggregate_from_model(model)
        except Exception as e:
            raise InfrastructureError(f"Failed to get order: {e}") from e
    
    async def delete(self, aggregate: Order) -> None:
        """Delete an order aggregate."""
        try:
            stmt = select(OrderModel).where(OrderModel.id == aggregate.id)
            result = await self._session.execute(stmt)
            model = result.scalar_one_or_none()
            
            if model:
                await self._session.delete(model)
                await self._session.commit()
        except Exception as e:
            await self._session.rollback()
            raise InfrastructureError(f"Failed to delete order: {e}") from e
    
    async def find_by_user_id(
        self,
        user_id: UUID,
        status: Optional[OrderStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Order]:
        """Find orders by user ID with optional status filter."""
        try:
            stmt = select(OrderModel).where(OrderModel.user_id == user_id)
            
            if status:
                stmt = stmt.where(OrderModel.status == status.value)
            
            stmt = stmt.limit(limit).offset(offset).order_by(OrderModel.created_at.desc())
            
            result = await self._session.execute(stmt)
            models = result.scalars().all()
            
            return [self._create_aggregate_from_model(model) for model in models]
        except Exception as e:
            raise InfrastructureError(f"Failed to find orders by user: {e}") from e
    
    async def find_by_symbol(
        self,
        symbol: Symbol,
        status: Optional[OrderStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Order]:
        """Find orders by symbol with optional status filter."""
        try:
            stmt = select(OrderModel).where(OrderModel.symbol == str(symbol))
            
            if status:
                stmt = stmt.where(OrderModel.status == status.value)
            
            stmt = stmt.limit(limit).offset(offset).order_by(OrderModel.created_at.desc())
            
            result = await self._session.execute(stmt)
            models = result.scalars().all()
            
            return [self._create_aggregate_from_model(model) for model in models]
        except Exception as e:
            raise InfrastructureError(f"Failed to find orders by symbol: {e}") from e
    
    async def find_active_orders(self, user_id: UUID) -> List[Order]:
        """Find all active (non-terminal) orders for a user."""
        try:
            active_statuses = [
                OrderStatus.PENDING.value,
                OrderStatus.SUBMITTED.value,
                OrderStatus.PARTIALLY_FILLED.value,
            ]
            
            stmt = select(OrderModel).where(
                and_(
                    OrderModel.user_id == user_id,
                    OrderModel.status.in_(active_statuses),
                )
            ).order_by(OrderModel.created_at.desc())
            
            result = await self._session.execute(stmt)
            models = result.scalars().all()
            
            return [self._create_aggregate_from_model(model) for model in models]
        except Exception as e:
            raise InfrastructureError(f"Failed to find active orders: {e}") from e
    
    def _create_model_from_aggregate(self, aggregate: Order) -> OrderModel:
        """Create SQLAlchemy model from domain aggregate."""
        return OrderModel(
            id=aggregate.id,
            user_id=aggregate.user_id,
            symbol=str(aggregate.symbol),
            side=aggregate.side.value,
            order_type=aggregate.order_type.value,
            quantity=str(aggregate.quantity.value),
            price=str(aggregate.price.value.amount) if aggregate.price else None,
            stop_price=str(aggregate.stop_price.value.amount) if aggregate.stop_price else None,
            time_in_force=aggregate.time_in_force.value,
            status=aggregate.status.value,
            filled_quantity=str(aggregate.filled_quantity.value),
            created_at=aggregate.created_at,
            updated_at=aggregate.updated_at,
        )
    
    def _update_model_from_aggregate(self, model: OrderModel, aggregate: Order) -> None:
        """Update SQLAlchemy model from domain aggregate."""
        model.status = aggregate.status.value
        model.filled_quantity = str(aggregate.filled_quantity.value)
        model.updated_at = aggregate.updated_at
    
    def _create_aggregate_from_model(self, model: OrderModel) -> Order:
        """Create domain aggregate from SQLAlchemy model."""
        from decimal import Decimal
        from ..domain.value_objects import (
            OrderSide,
            OrderStatus,
            OrderType,
            Price,
            Quantity,
            Symbol,
            TimeInForce,
        )
        from ....shared.utils.money import Money
        
        # Create value objects
        symbol = Symbol(model.symbol)
        side = OrderSide(model.side)
        order_type = OrderType(model.order_type)
        quantity = Quantity(Decimal(model.quantity))
        time_in_force = TimeInForce(model.time_in_force)
        
        price = None
        if model.price:
            price = Price(Money(model.price))
        
        stop_price = None
        if model.stop_price:
            stop_price = Price(Money(model.stop_price))
        
        # Create order (this will be in PENDING state initially)
        order = Order(
            user_id=model.user_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            time_in_force=time_in_force,
            id=model.id,
        )
        
        # Set the actual status and filled quantity from the model
        order._status = OrderStatus(model.status)
        order._filled_quantity = Quantity(Decimal(model.filled_quantity))
        order._created_at = model.created_at
        order._updated_at = model.updated_at
        
        return order