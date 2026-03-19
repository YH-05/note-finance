"""academic パッケージのカスタム例外階層.

HTTP ステータスコードに基づいた例外分類を提供する。
"""


class AcademicError(Exception):
    """academic パッケージの基底例外."""

    pass


class RetryableError(AcademicError):
    """リトライで回復可能なエラー（429, 5xx, タイムアウト, 接続エラー）."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


class PermanentError(AcademicError):
    """リトライしても回復不可能なエラー（403, 404, パース失敗）."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code


class RateLimitError(RetryableError):
    """レート制限エラー（HTTP 429）."""

    pass


class PaperNotFoundError(PermanentError):
    """論文が見つからないエラー（HTTP 404）."""

    pass


class ParseError(AcademicError):
    """レスポンスのパース失敗."""

    pass


__all__ = [
    "AcademicError",
    "PaperNotFoundError",
    "ParseError",
    "PermanentError",
    "RateLimitError",
    "RetryableError",
]
