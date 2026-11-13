"""RabbitMQ messaging for DevSphere operations."""

import json
import logging

import pika

from app.core.config import settings


logger = logging.getLogger(__name__)


def open_connection():
    credentials = pika.PlainCredentials(
        settings.rabbitmq_user,
        settings.rabbitmq_password,
    )

    return pika.BlockingConnection(
        pika.ConnectionParameters(
            host=settings.rabbitmq_host,
            port=settings.rabbitmq_port,
            credentials=credentials,
            heartbeat=60,
            blocked_connection_timeout=15,
            connection_attempts=3,
            retry_delay=2,
        )
    )


def declare_queue(channel):
    channel.queue_declare(
        queue=settings.operation_queue,
        durable=True,
    )


def publish_operation(operation_id: str):
    connection = open_connection()

    try:
        channel = connection.channel()
        declare_queue(channel)
        channel.confirm_delivery()

        payload = json.dumps({
            "operation_id": operation_id,
        }).encode("utf-8")

        channel.basic_publish(
            exchange="",
            routing_key=settings.operation_queue,
            body=payload,
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type="application/json",
                message_id=operation_id,
            ),
            mandatory=True,
        )

        logger.info(
            "Operation published successfully: %s",
            operation_id,
        )

    finally:
        if connection.is_open:
            connection.close()
