#!/usr/bin/env python3
"""Development environment setup script."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from infrastructure.persistence.database import DatabaseManager


async def setup_database():
    """Set up development database."""
    print("Setting up development database...")
    
    db_manager = DatabaseManager("postgresql+asyncpg://tradesense:password@localhost/tradesense")
    
    try:
        # Create tables
        await db_manager.create_tables()
        print("✅ Database tables created successfully")
        
    except Exception as e:
        print(f"❌ Failed to create database tables: {e}")
        return False
    
    finally:
        await db_manager.close()
    
    return True


async def main():
    """Main setup function."""
    print("🚀 Setting up TradeSense AI development environment")
    
    # Setup database
    if not await setup_database():
        sys.exit(1)
    
    print("\n✅ Development environment setup complete!")
    print("\nNext steps:")
    print("1. Start Redis: redis-server")
    print("2. Start the application: python -m src.main")
    print("3. Visit http://localhost:8000/docs for API documentation")


if __name__ == "__main__":
    asyncio.run(main())