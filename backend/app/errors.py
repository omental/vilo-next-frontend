class InvoiceValidationError(Exception):
    def __init__(self, errors: list[dict[str, str]], *, status_code: int = 422):
        super().__init__("Invoice validation failed")
        self.errors = errors
        self.status_code = status_code
