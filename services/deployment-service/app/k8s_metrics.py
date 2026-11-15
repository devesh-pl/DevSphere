"""Lightweight Kubernetes metrics for DevSphere workloads."""

import logging

from kubernetes.client.exceptions import ApiException
from prometheus_client import REGISTRY
from prometheus_client.core import GaugeMetricFamily

from app.main import NAMESPACE, apps_api, core_api


logger = logging.getLogger("devsphere.k8s.metrics")


class DevSphereKubernetesCollector:
    def describe(self):
        # Do not query Kubernetes during collector registration.
        return []

    def collect(self):
        success = GaugeMetricFamily(
            "devsphere_k8s_collection_success",
            "Whether Kubernetes metrics collection succeeded",
        )

        desired = GaugeMetricFamily(
            "devsphere_k8s_deployment_desired_replicas",
            "Desired deployment replicas",
            labels=["namespace", "deployment"],
        )

        ready = GaugeMetricFamily(
            "devsphere_k8s_deployment_ready_replicas",
            "Ready deployment replicas",
            labels=["namespace", "deployment"],
        )

        pod_ready = GaugeMetricFamily(
            "devsphere_k8s_pod_ready",
            "Whether the pod containers are ready",
            labels=["namespace", "pod"],
        )

        restarts = GaugeMetricFamily(
            "devsphere_k8s_pod_restarts",
            "Container restarts reported for a pod",
            labels=["namespace", "pod"],
        )

        try:
            deployments = apps_api.list_namespaced_deployment(
                namespace=NAMESPACE,
                label_selector="app.kubernetes.io/managed-by=devsphere",
                _request_timeout=8,
            ).items

            pods = core_api.list_namespaced_pod(
                namespace=NAMESPACE,
                label_selector="app.kubernetes.io/managed-by=devsphere",
                _request_timeout=8,
            ).items

            for deployment in deployments:
                name = deployment.metadata.name
                desired_count = deployment.spec.replicas or 0
                ready_count = deployment.status.ready_replicas or 0

                desired.add_metric(
                    [NAMESPACE, name], desired_count
                )
                ready.add_metric(
                    [NAMESPACE, name], ready_count
                )

            for pod in pods:
                name = pod.metadata.name
                statuses = pod.status.container_statuses or []

                is_ready = bool(statuses) and all(
                    container.ready for container in statuses
                )

                restart_count = sum(
                    container.restart_count or 0
                    for container in statuses
                )

                pod_ready.add_metric(
                    [NAMESPACE, name], int(is_ready)
                )
                restarts.add_metric(
                    [NAMESPACE, name], restart_count
                )

            success.add_metric([], 1)

        except (ApiException, OSError, ValueError):
            logger.exception("Kubernetes metrics collection failed")
            success.add_metric([], 0)

        yield success
        yield desired
        yield ready
        yield pod_ready
        yield restarts


def register_kubernetes_metrics():
    REGISTRY.register(DevSphereKubernetesCollector())
