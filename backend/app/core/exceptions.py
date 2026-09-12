class AppError(Exception):
    """Controlled application error safe to expose through the API."""

    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code

    def as_dict(self):
        return {"error": {"code": self.code, "message": self.message}}

