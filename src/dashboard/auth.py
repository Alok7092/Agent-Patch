import bcrypt
from itsdangerous import URLSafeTimedSerializer


class AuthManager:
    def __init__(self, secret_key: str, users: list[dict]):
        self.serializer = URLSafeTimedSerializer(secret_key)
        self.users = {u["username"]: u for u in users}
        if "admin" in self.users and not self.users["admin"].get("password_hash"):
            self.users["admin"]["password_hash"] = bcrypt.hashpw(
                b"admin", bcrypt.gensalt()
            ).decode("utf-8")

    def verify_password(self, username: str, password: str) -> bool:
        user = self.users.get(username)
        if not user:
            return False
        stored_hash = user["password_hash"].encode("utf-8")
        return bcrypt.checkpw(password.encode("utf-8"), stored_hash)

    def get_user_role(self, username: str) -> str:
        user = self.users.get(username)
        return user.get("role", "viewer") if user else "viewer"

    def create_session_token(self, username: str) -> str:
        return self.serializer.dumps({"username": username})

    def validate_session_token(self, token: str, max_age: int = 86400) -> str | None:
        try:
            data = self.serializer.loads(token, max_age=max_age)
            return data["username"]
        except Exception:
            return None
