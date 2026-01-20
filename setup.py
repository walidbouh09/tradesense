#!/usr/bin/env python3
"""
TradeSense AI - Professional Setup Script

This script provides a comprehensive setup process for the TradeSense AI
prop trading platform, including dependency installation, database setup,
and environment configuration.
"""

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional


# ANSI color codes for better output
class Colors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def print_colored(message: str, color: str = Colors.ENDC):
    """Print colored message."""
    print(f"{color}{message}{Colors.ENDC}")


def print_header(title: str):
    """Print section header."""
    print()
    print_colored("=" * 60, Colors.HEADER)
    print_colored(f" {title}", Colors.HEADER)
    print_colored("=" * 60, Colors.HEADER)
    print()


def print_step(step: str):
    """Print setup step."""
    print_colored(f"📋 {step}", Colors.OKBLUE)


def print_success(message: str):
    """Print success message."""
    print_colored(f"✅ {message}", Colors.OKGREEN)


def print_warning(message: str):
    """Print warning message."""
    print_colored(f"⚠️  {message}", Colors.WARNING)


def print_error(message: str):
    """Print error message."""
    print_colored(f"❌ {message}", Colors.FAIL)


def run_command(command: List[str], description: str, check: bool = True) -> bool:
    """Run shell command with error handling."""
    try:
        print_step(f"{description}...")
        result = subprocess.run(command, capture_output=True, text=True, check=check)

        if result.returncode == 0:
            print_success(f"{description} completed")
            return True
        else:
            print_error(f"{description} failed")
            if result.stderr:
                print(result.stderr)
            return False

    except subprocess.CalledProcessError as e:
        print_error(f"{description} failed: {e}")
        if e.stderr:
            print(e.stderr)
        return False
    except FileNotFoundError:
        print_error(f"Command not found: {' '.join(command)}")
        return False


def check_python_version():
    """Check if Python version is compatible."""
    print_step("Checking Python version...")

    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print_error(f"Python 3.8+ required, found {version.major}.{version.minor}")
        return False

    print_success(
        f"Python {version.major}.{version.minor}.{version.micro} is compatible"
    )
    return True


def check_system_dependencies():
    """Check for required system dependencies."""
    print_step("Checking system dependencies...")

    dependencies = {
        "git": "git --version",
        "node": "node --version",
        "npm": "npm --version",
    }

    missing = []
    for dep, check_cmd in dependencies.items():
        try:
            subprocess.run(check_cmd.split(), capture_output=True, check=True)
            print_success(f"{dep} is installed")
        except (subprocess.CalledProcessError, FileNotFoundError):
            missing.append(dep)
            print_warning(f"{dep} is not installed")

    if missing:
        print_error("Missing dependencies:")
        for dep in missing:
            print(f"  - {dep}")

        print_colored("\nPlease install missing dependencies:", Colors.WARNING)
        if platform.system() == "Windows":
            print("  - Install Git: https://git-scm.com/download/win")
            print("  - Install Node.js: https://nodejs.org/")
        elif platform.system() == "Darwin":  # macOS
            print(
                '  - Install Homebrew: /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
            )
            print("  - brew install git node npm")
        else:  # Linux
            print("  - sudo apt update && sudo apt install git nodejs npm")
            print("  - Or use your distribution's package manager")

        return False

    return True


def setup_python_environment():
    """Setup Python virtual environment and install dependencies."""
    print_step("Setting up Python environment...")

    # Create virtual environment if it doesn't exist
    venv_path = Path(".venv")
    if not venv_path.exists():
        if not run_command(
            [sys.executable, "-m", "venv", ".venv"], "Creating virtual environment"
        ):
            return False
    else:
        print_success("Virtual environment already exists")

    # Determine activation script based on OS
    if platform.system() == "Windows":
        pip_path = venv_path / "Scripts" / "pip"
        python_path = venv_path / "Scripts" / "python"
    else:
        pip_path = venv_path / "bin" / "pip"
        python_path = venv_path / "bin" / "python"

    # Upgrade pip
    if not run_command(
        [str(python_path), "-m", "pip", "install", "--upgrade", "pip"], "Upgrading pip"
    ):
        return False

    # Install requirements
    if Path("requirements.txt").exists():
        if not run_command(
            [str(pip_path), "install", "-r", "requirements.txt"],
            "Installing Python dependencies",
        ):
            return False
    else:
        print_warning("requirements.txt not found, installing basic dependencies")
        basic_deps = [
            "Flask==3.0.0",
            "Flask-CORS==4.0.0",
            "Flask-SocketIO==5.3.6",
            "Flask-JWT-Extended==4.6.0",
            "Flask-SQLAlchemy==3.1.1",
            "psycopg2-binary==2.9.9",
            "redis==5.0.1",
            "celery==5.3.4",
            "python-dotenv==1.0.0",
        ]

        for dep in basic_deps:
            if not run_command([str(pip_path), "install", dep], f"Installing {dep}"):
                return False

    return True


def setup_frontend_environment():
    """Setup frontend Node.js environment."""
    print_step("Setting up frontend environment...")

    frontend_path = Path("frontend")
    if not frontend_path.exists():
        print_warning("Frontend directory not found, skipping frontend setup")
        return True

    # Change to frontend directory
    original_dir = Path.cwd()
    os.chdir(frontend_path)

    try:
        # Install npm dependencies
        if not run_command(["npm", "install"], "Installing frontend dependencies"):
            return False

        print_success("Frontend environment setup completed")
        return True

    finally:
        # Return to original directory
        os.chdir(original_dir)


def setup_environment_file():
    """Setup environment configuration file."""
    print_step("Setting up environment configuration...")

    env_example = Path(".env.example")
    env_file = Path(".env")

    if env_example.exists() and not env_file.exists():
        shutil.copy(env_example, env_file)
        print_success("Created .env file from .env.example")

        print_colored(
            "\n📝 Please edit the .env file with your configuration:", Colors.WARNING
        )
        print("   - Database connection string")
        print("   - Secret keys")
        print("   - API keys")
        print("   - Email settings")

        return True
    elif env_file.exists():
        print_success("Environment file already exists")
        return True
    else:
        print_warning("No .env.example found, creating basic .env file")

        basic_env = """# TradeSense AI Configuration
FLASK_ENV=development
FLASK_DEBUG=True
SECRET_KEY=dev-secret-key-change-in-production
DATABASE_URL=postgresql://tradesense:password123@localhost:5432/tradesense_db
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=jwt-secret-key-change-in-production
CORS_ORIGINS=http://localhost:3000,http://localhost:3001,http://localhost:5173
"""

        with open(env_file, "w") as f:
            f.write(basic_env)

        print_success("Created basic .env file")
        return True


def create_directories():
    """Create necessary directories."""
    print_step("Creating necessary directories...")

    directories = ["logs", "uploads", "backups", "static/uploads"]

    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)

    print_success("Created necessary directories")
    return True


def setup_database():
    """Setup database tables and initial data."""
    print_step("Setting up database...")

    # Check if init_db.py exists
    if not Path("init_db.py").exists():
        print_warning("init_db.py not found, skipping database initialization")
        print(
            "You can manually create tables using Flask-Migrate or create the init_db.py script"
        )
        return True

    # Get Python path from virtual environment
    if platform.system() == "Windows":
        python_path = Path(".venv") / "Scripts" / "python"
    else:
        python_path = Path(".venv") / "bin" / "python"

    if python_path.exists():
        if run_command(
            [str(python_path), "init_db.py"], "Initializing database", check=False
        ):
            print_success("Database initialized successfully")
            return True
        else:
            print_warning(
                "Database initialization failed, you may need to set it up manually"
            )
            return True
    else:
        print_warning("Virtual environment not found, using system Python")
        if run_command(
            [sys.executable, "init_db.py"], "Initializing database", check=False
        ):
            print_success("Database initialized successfully")
            return True
        else:
            print_warning("Database initialization failed")
            return True


def print_next_steps():
    """Print next steps after setup."""
    print_header("Setup Complete! Next Steps")

    print_colored("🚀 To start the application:", Colors.OKGREEN)
    print()

    if platform.system() == "Windows":
        print("  Backend (API Server):")
        print("    .venv\\Scripts\\activate")
        print("    python run.py")
        print()
    else:
        print("  Backend (API Server):")
        print("    source .venv/bin/activate")
        print("    python run.py")
        print()

    if Path("frontend").exists():
        print("  Frontend (React App):")
        print("    cd frontend")
        print("    npm start")
        print()

    print_colored("📖 Configuration:", Colors.OKBLUE)
    print("  - Edit .env file with your database and API keys")
    print("  - Update CORS settings if needed")
    print("  - Configure email settings for notifications")
    print()

    print_colored("🌐 Access URLs:", Colors.OKCYAN)
    print("  - Backend API: http://localhost:5000")
    print("  - API Health Check: http://localhost:5000/health")
    if Path("frontend").exists():
        print("  - Frontend App: http://localhost:3000")
    print()

    print_colored("🔑 Demo Credentials (after database setup):", Colors.WARNING)
    print("  - Admin: admin@tradesense.ai / admin123456")
    print("  - Demo Trader: demo.trader@tradesense.ai / demo123456")
    print()

    print_colored("📚 Documentation:", Colors.OKBLUE)
    print("  - API Documentation: http://localhost:5000/docs")
    print("  - WebSocket endpoint: ws://localhost:5000/ws")
    print()


def main():
    """Main setup function."""
    print_colored(
        """
 ████████╗██████╗  █████╗ ██████╗ ███████╗███████╗███████╗███╗   ██╗███████╗███████╗
 ╚══██╔══╝██╔══██╗██╔══██╗██╔══██╗██╔════╝██╔════╝██╔════╝████╗  ██║██╔════╝██╔════╝
    ██║   ██████╔╝███████║██║  ██║█████╗  ███████╗█████╗  ██╔██╗ ██║███████╗█████╗
    ██║   ██╔══██╗██╔══██║██║  ██║██╔══╝  ╚════██║██╔══╝  ██║╚██╗██║╚════██║██╔══╝
    ██║   ██║  ██║██║  ██║██████╔╝███████╗███████║███████╗██║ ╚████║███████║███████╗
    ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚══════╝╚══════╝╚══════╝╚═╝  ╚═══╝╚══════╝╚══════╝

    🚀 Professional Prop Trading Platform Setup
    """,
        Colors.HEADER,
    )

    print_colored(
        "Welcome to TradeSense AI setup! This will configure your development environment.",
        Colors.OKBLUE,
    )
    print()

    # Check prerequisites
    print_header("Checking Prerequisites")

    if not check_python_version():
        return False

    if not check_system_dependencies():
        return False

    # Setup environments
    print_header("Setting Up Environments")

    if not setup_python_environment():
        return False

    if not setup_frontend_environment():
        return False

    # Setup configuration
    print_header("Configuration Setup")

    if not setup_environment_file():
        return False

    if not create_directories():
        return False

    # Setup database
    print_header("Database Setup")

    if not setup_database():
        print_warning("Database setup had issues, but continuing...")

    # Success!
    print_header("🎉 Setup Successful!")
    print_next_steps()

    return True


if __name__ == "__main__":
    try:
        success = main()
        if success:
            print_colored(
                "\n✅ TradeSense AI setup completed successfully!", Colors.OKGREEN
            )
            sys.exit(0)
        else:
            print_colored(
                "\n❌ Setup failed. Please check the errors above.", Colors.FAIL
            )
            sys.exit(1)
    except KeyboardInterrupt:
        print_colored("\n\n⚠️  Setup interrupted by user", Colors.WARNING)
        sys.exit(1)
    except Exception as e:
        print_colored(f"\n💥 Unexpected error during setup: {e}", Colors.FAIL)
        sys.exit(1)
