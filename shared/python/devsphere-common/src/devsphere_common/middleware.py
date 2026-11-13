import logging
import time

from fastapi import FastAPI, Request

from devsphere_common.correlation import (
    CORRELATION_ID_HEADER,
    resolve_correlation_id,
)


def install_correlation_id_middleware(
    app: FastAPI,
    service_name: str,
):

    logger = logging.getLogger("devsphere.request")

    @app.middleware("http")
    async def correlation_id_middleware(
        request: Request,
        call_next,
    ):

        incoming_id = request.headers.get(
            CORRELATION_ID_HEADER
        )

        correlation_id = resolve_correlation_id(
            incoming_id
        )

        request.state.correlation_id = correlation_id

        start_time = time.perf_counter()

        try:

            response = await call_next(request)

        except Exception:

            logger.exception(
                "request_failed",
                extra={
                    "service": service_name,
                    "correlation_id": correlation_id,
                    "method": request.method,
                    "path": request.url.path,
                },
            )

            raise

        duration_ms = round(
            (time.perf_counter() - start_time) * 1000,
            2,
        )

        response.headers[CORRELATION_ID_HEADER] = (
            correlation_id
        )

        logger.info(
            "request_completed",
            extra={
                "service": service_name,
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )

        return response