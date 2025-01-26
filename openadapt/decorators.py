import sqlalchemy as sa


# https://groups.google.com/g/sqlalchemy/c/wlr7sShU6-k
class ForceFloat(sa.TypeDecorator):
    """Custom SQLAlchemy type decorator for floating-point numbers."""

    impl = sa.Numeric(10, 2, asdecimal=False)
    cache_ok = True

    def process_result_value(
        self,
        value: int | float | str | None,
        dialect: str,
    ) -> float | None:
        """Convert the result value to float."""
        if value is not None:
            value = float(value)
        return value
