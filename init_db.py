#!/usr/bin/env python3
"""
TradeSense AI - Database Initialization Script

Professional database setup with proper tables, relationships, indexes,
and initial data for the trading platform.
"""

import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import logging
from datetime import datetime, timezone
from decimal import Decimal

from app import create_app
from app.models import (
    Challenge,
    ChallengeStatus,
    MarketData,
    Notification,
    NotificationStatus,
    Payment,
    PaymentStatus,
    Portfolio,
    RiskAssessment,
    RiskLevel,
    Trade,
    User,
    UserRole,
    UserStatus,
    db,
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_database_tables():
    """Create all database tables."""
    try:
        logger.info("Creating database tables...")
        db.create_all()
        logger.info("✅ Database tables created successfully")
    except Exception as e:
        logger.error(f"❌ Error creating database tables: {e}")
        raise


def create_admin_user():
    """Create default admin user."""
    try:
        # Check if admin already exists
        admin_email = "admin@tradesense.ai"
        existing_admin = User.query.filter_by(email=admin_email).first()

        if existing_admin:
            logger.info("Admin user already exists")
            return existing_admin

        # Create admin user
        admin_user = User(
            email=admin_email,
            first_name="Admin",
            last_name="TradeSense",
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
            is_verified=True,
            experience_level="advanced",
            country="USA",
        )
        admin_user.set_password("admin123456")

        db.session.add(admin_user)
        db.session.commit()

        logger.info(f"✅ Admin user created: {admin_email}")
        return admin_user

    except Exception as e:
        logger.error(f"❌ Error creating admin user: {e}")
        db.session.rollback()
        raise


def create_demo_users():
    """Create demo users for testing."""
    demo_users = [
        {
            "email": "demo.trader@tradesense.ai",
            "first_name": "Demo",
            "last_name": "Trader",
            "role": UserRole.TRADER,
            "experience_level": "intermediate",
        },
        {
            "email": "john.doe@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "role": UserRole.TRADER,
            "experience_level": "beginner",
        },
        {
            "email": "jane.smith@example.com",
            "first_name": "Jane",
            "last_name": "Smith",
            "role": UserRole.TRADER,
            "experience_level": "advanced",
        },
    ]

    created_users = []

    for user_data in demo_users:
        try:
            # Check if user already exists
            existing_user = User.query.filter_by(email=user_data["email"]).first()
            if existing_user:
                logger.info(f"User {user_data['email']} already exists")
                created_users.append(existing_user)
                continue

            # Create new user
            user = User(
                email=user_data["email"],
                first_name=user_data["first_name"],
                last_name=user_data["last_name"],
                role=user_data["role"],
                status=UserStatus.ACTIVE,
                is_verified=True,
                experience_level=user_data["experience_level"],
                country="USA",
            )
            user.set_password("demo123456")

            db.session.add(user)
            created_users.append(user)

        except Exception as e:
            logger.error(f"❌ Error creating user {user_data['email']}: {e}")
            db.session.rollback()
            continue

    try:
        db.session.commit()
        logger.info(f"✅ Created {len(created_users)} demo users")
        return created_users
    except Exception as e:
        logger.error(f"❌ Error saving demo users: {e}")
        db.session.rollback()
        return []


def create_demo_portfolios(users):
    """Create demo portfolios for users."""
    portfolios = []

    for user in users:
        if user.role == UserRole.TRADER:
            try:
                # Check if user already has portfolios
                existing_portfolio = Portfolio.query.filter_by(user_id=user.id).first()
                if existing_portfolio:
                    logger.info(f"Portfolio already exists for user {user.email}")
                    portfolios.append(existing_portfolio)
                    continue

                # Create demo portfolio
                portfolio = Portfolio(
                    name=f"{user.first_name}'s Trading Portfolio",
                    description="Demo trading portfolio for development and testing",
                    user_id=user.id,
                    initial_balance=Decimal("10000.00"),
                    current_balance=Decimal("10000.00"),
                    available_balance=Decimal("10000.00"),
                    is_demo=True,
                    is_active=True,
                )

                db.session.add(portfolio)
                portfolios.append(portfolio)

            except Exception as e:
                logger.error(f"❌ Error creating portfolio for user {user.email}: {e}")
                continue

    try:
        db.session.commit()
        logger.info(f"✅ Created {len(portfolios)} demo portfolios")
        return portfolios
    except Exception as e:
        logger.error(f"❌ Error saving portfolios: {e}")
        db.session.rollback()
        return []


def create_demo_challenges(users):
    """Create demo challenges."""
    challenges = []

    challenge_templates = [
        {
            "name": "Beginner Trading Challenge",
            "description": "Perfect for new traders to test their skills",
            "initial_balance": Decimal("5000.00"),
            "target_profit": Decimal("400.00"),  # 8% target
            "max_loss": Decimal("500.00"),  # 10% max loss
            "duration_days": 30,
            "entry_fee": Decimal("99.00"),
        },
        {
            "name": "Intermediate Challenge",
            "description": "For experienced traders seeking funded accounts",
            "initial_balance": Decimal("25000.00"),
            "target_profit": Decimal("2000.00"),  # 8% target
            "max_loss": Decimal("2500.00"),  # 10% max loss
            "duration_days": 60,
            "entry_fee": Decimal("299.00"),
        },
        {
            "name": "Pro Trader Challenge",
            "description": "Elite challenge for professional traders",
            "initial_balance": Decimal("100000.00"),
            "target_profit": Decimal("8000.00"),  # 8% target
            "max_loss": Decimal("10000.00"),  # 10% max loss
            "duration_days": 90,
            "entry_fee": Decimal("599.00"),
        },
    ]

    for i, template in enumerate(challenge_templates):
        try:
            # Assign to different users
            user = users[i % len(users)] if users else None
            if not user or user.role != UserRole.TRADER:
                continue

            # Check if challenge already exists
            existing_challenge = Challenge.query.filter_by(
                name=template["name"], user_id=user.id
            ).first()
            if existing_challenge:
                logger.info(f"Challenge '{template['name']}' already exists")
                challenges.append(existing_challenge)
                continue

            # Create challenge
            challenge = Challenge(
                name=template["name"],
                description=template["description"],
                user_id=user.id,
                initial_balance=template["initial_balance"],
                target_profit=template["target_profit"],
                max_loss=template["max_loss"],
                duration_days=template["duration_days"],
                entry_fee=template["entry_fee"],
                status=ChallengeStatus.ACTIVE,
                current_balance=template["initial_balance"],
                start_date=datetime.now(timezone.utc),
            )

            db.session.add(challenge)
            challenges.append(challenge)

        except Exception as e:
            logger.error(f"❌ Error creating challenge '{template['name']}': {e}")
            continue

    try:
        db.session.commit()
        logger.info(f"✅ Created {len(challenges)} demo challenges")
        return challenges
    except Exception as e:
        logger.error(f"❌ Error saving challenges: {e}")
        db.session.rollback()
        return []


def create_sample_market_data():
    """Create sample market data for testing."""
    symbols = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"]
    timeframes = ["1m", "5m", "15m", "1h", "4h", "1d"]

    market_data_entries = []

    for symbol in symbols:
        for timeframe in timeframes:
            try:
                # Check if data already exists
                existing_data = MarketData.query.filter_by(
                    symbol=symbol, timeframe=timeframe
                ).first()
                if existing_data:
                    continue

                # Create sample data point
                base_price = 1.1000 if "EUR" in symbol else 1.0000

                market_data = MarketData(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=datetime.now(timezone.utc),
                    open_price=Decimal(str(base_price)),
                    high_price=Decimal(str(base_price + 0.0050)),
                    low_price=Decimal(str(base_price - 0.0050)),
                    close_price=Decimal(str(base_price + 0.0025)),
                    volume=Decimal("1000000.0"),
                )

                db.session.add(market_data)
                market_data_entries.append(market_data)

            except Exception as e:
                logger.error(f"❌ Error creating market data for {symbol}: {e}")
                continue

    try:
        db.session.commit()
        logger.info(f"✅ Created {len(market_data_entries)} sample market data entries")
        return market_data_entries
    except Exception as e:
        logger.error(f"❌ Error saving market data: {e}")
        db.session.rollback()
        return []


def create_sample_notifications(users):
    """Create sample notifications for users."""
    notifications = []

    notification_templates = [
        {
            "title": "Welcome to TradeSense AI",
            "message": "Welcome to the future of prop trading! Start your journey with our demo challenges.",
            "type": "welcome",
            "priority": "normal",
        },
        {
            "title": "Market Alert: High Volatility",
            "message": "EUR/USD is experiencing high volatility. Review your risk management settings.",
            "type": "market",
            "priority": "high",
        },
        {
            "title": "Challenge Update",
            "message": "Your trading challenge is performing well! You're on track to meet your profit target.",
            "type": "challenge",
            "priority": "normal",
        },
    ]

    for user in users:
        if user.role == UserRole.TRADER:
            for template in notification_templates:
                try:
                    notification = Notification(
                        user_id=user.id,
                        title=template["title"],
                        message=template["message"],
                        type=template["type"],
                        priority=template["priority"],
                        status=NotificationStatus.UNREAD,
                    )

                    db.session.add(notification)
                    notifications.append(notification)

                except Exception as e:
                    logger.error(
                        f"❌ Error creating notification for user {user.email}: {e}"
                    )
                    continue

    try:
        db.session.commit()
        logger.info(f"✅ Created {len(notifications)} sample notifications")
        return notifications
    except Exception as e:
        logger.error(f"❌ Error saving notifications: {e}")
        db.session.rollback()
        return []


def initialize_database():
    """Initialize the complete database with tables and sample data."""
    logger.info("🚀 Starting TradeSense AI database initialization...")

    try:
        # Create tables
        create_database_tables()

        # Create admin user
        admin_user = create_admin_user()

        # Create demo users
        demo_users = create_demo_users()
        all_users = [admin_user] + demo_users

        # Create portfolios
        portfolios = create_demo_portfolios(all_users)

        # Create challenges
        challenges = create_demo_challenges(demo_users)

        # Create sample market data
        market_data = create_sample_market_data()

        # Create sample notifications
        notifications = create_sample_notifications(demo_users)

        logger.info("✅ Database initialization completed successfully!")
        logger.info(f"📊 Summary:")
        logger.info(f"   - Users: {len(all_users)}")
        logger.info(f"   - Portfolios: {len(portfolios)}")
        logger.info(f"   - Challenges: {len(challenges)}")
        logger.info(f"   - Market data entries: {len(market_data)}")
        logger.info(f"   - Notifications: {len(notifications)}")

        # Print login credentials
        logger.info("🔐 Demo Login Credentials:")
        logger.info("   Admin: admin@tradesense.ai / admin123456")
        logger.info("   Demo Trader: demo.trader@tradesense.ai / demo123456")
        logger.info("   John Doe: john.doe@example.com / demo123456")
        logger.info("   Jane Smith: jane.smith@example.com / demo123456")

        return True

    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        return False


def reset_database():
    """Drop all tables and recreate them."""
    logger.warning("⚠️  Resetting database - all data will be lost!")

    try:
        db.drop_all()
        logger.info("🗑️  Dropped all tables")

        return initialize_database()

    except Exception as e:
        logger.error(f"❌ Database reset failed: {e}")
        return False


def main():
    """Main function to run the database initialization."""
    # Create Flask app
    app = create_app("development")

    with app.app_context():
        if len(sys.argv) > 1 and sys.argv[1] == "--reset":
            success = reset_database()
        else:
            success = initialize_database()

        if success:
            logger.info("🎉 Database setup completed successfully!")
            sys.exit(0)
        else:
            logger.error("💥 Database setup failed!")
            sys.exit(1)


if __name__ == "__main__":
    main()
