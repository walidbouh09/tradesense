from flask import Flask, jsonify, request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, User, Portfolio, Trade

DATABASE_URL = "sqlite:///../tradesense.db"

engine = create_engine(DATABASE_URL, echo=False, future=True)
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

app = Flask(__name__)


@app.route("/health")
def health():
    return jsonify({"status": "healthy", "service": "backend"})


@app.route("/api/users", methods=["GET", "POST"])
def users():
    session = SessionLocal()
    if request.method == "POST":
        data = request.get_json() or {}
        user = User(name=data.get("name", "Unnamed"), email=data.get("email"))
        session.add(user)
        session.commit()
        return jsonify({"id": user.id, "name": user.name}), 201

    users = session.query(User).all()
    result = [{"id": u.id, "name": u.name, "email": u.email} for u in users]
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
