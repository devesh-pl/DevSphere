package com.devsphere.deployment.kubernetes;
import com.devsphere.common.ApiException;
import io.fabric8.kubernetes.api.model.*;
import io.fabric8.kubernetes.api.model.apps.*;
import io.fabric8.kubernetes.client.*;
import io.fabric8.kubernetes.client.dsl.base.*;
import io.fabric8.kubernetes.client.utils.Serialization;
import java.util.*;
import org.springframework.stereotype.Component;
@Component
public class Workloads {
  public static final String NS = "devsphere-apps";
  private final KubernetesClient client;
  public Workloads(KubernetesClient client) {
    this.client = client;
  }
  public static boolean allowed(String image) {
    return image != null
        && (image.equals("nginxinc/nginx-unprivileged:stable-alpine")
            || image.matches("devsphere-built/[a-z][a-z0-9-]{2,62}:[a-f0-9]{8,32}"));
  }
  public Map<String, String> labels(com.devsphere.deployment.entity.Deployment d) {
    return Map.of("app", d.name, "app.kubernetes.io/managed-by", "devsphere-java",
        "devsphere.io/owner", d.ownerId, "devsphere.io/deployment", d.id);
  }
  public void create(com.devsphere.deployment.entity.Deployment d) {
    var labels = labels(d);
    var container =
        new ContainerBuilder()
            .withName("application")
            .withImage(d.image)
            .withImagePullPolicy("IfNotPresent")
            .withPorts(new ContainerPortBuilder().withContainerPort(d.containerPort).build())
            .withResources(new ResourceRequirementsBuilder()
                    .addToRequests("cpu", new Quantity("25m"))
                    .addToRequests("memory", new Quantity("32Mi"))
                    .addToLimits("cpu", new Quantity("200m"))
                    .addToLimits("memory", new Quantity("128Mi"))
                    .build())
            .withSecurityContext(new SecurityContextBuilder()
                    .withAllowPrivilegeEscalation(false)
                    .withRunAsNonRoot(true)
                    .withRunAsUser(101L)
                    .withCapabilities(new CapabilitiesBuilder().withDrop("ALL").build())
                    .withSeccompProfile(
                        new SeccompProfileBuilder().withType("RuntimeDefault").build())
                    .build())
            .withReadinessProbe(new ProbeBuilder()
                    .withHttpGet(new HTTPGetActionBuilder()
                            .withPath("/")
                            .withPort(new IntOrString(d.containerPort))
                            .build())
                    .withInitialDelaySeconds(3)
                    .withPeriodSeconds(5)
                    .build())
            .build();
    var deployment = new DeploymentBuilder()
                         .withNewMetadata()
                         .withName(d.name)
                         .withNamespace(NS)
                         .withLabels(labels)
                         .endMetadata()
                         .withNewSpec()
                         .withReplicas(d.replicas)
                         .withProgressDeadlineSeconds(120)
                         .withNewSelector()
                         .addToMatchLabels("app", d.name)
                         .endSelector()
                         .withNewTemplate()
                         .withNewMetadata()
                         .withLabels(labels)
                         .endMetadata()
                         .withNewSpec()
                         .withAutomountServiceAccountToken(false)
                         .withContainers(container)
                         .endSpec()
                         .endTemplate()
                         .endSpec()
                         .build();
    var service = new ServiceBuilder()
                      .withNewMetadata()
                      .withName(d.name)
                      .withNamespace(NS)
                      .withLabels(labels)
                      .endMetadata()
                      .withNewSpec()
                      .withType("ClusterIP")
                      .withSelector(Map.of("app", d.name))
                      .withPorts(new ServicePortBuilder()
                              .withPort(d.containerPort)
                              .withTargetPort(new IntOrString(d.containerPort))
                              .build())
                      .endSpec()
                      .build();
    try {
      client.apps().deployments().inNamespace(NS).resource(deployment).create();
      client.services().inNamespace(NS).resource(service).create();
    } catch (KubernetesClientException e) {
      throw new ApiException(
          502, "Kubernetes creation failed; inspect failed deployment before retrying");
    }
  }
  private void check(com.devsphere.deployment.entity.Deployment d, HasMetadata resource) {
    if (!NS.equals(d.namespace) || resource.getMetadata().getLabels() == null
        || !resource.getMetadata().getLabels().entrySet().containsAll(labels(d).entrySet()))
      throw new ApiException(409, "Kubernetes ownership labels do not match");
  }
  public io.fabric8.kubernetes.api.model.apps.Deployment read(
      com.devsphere.deployment.entity.Deployment d) {
    try {
      var resource = client.apps().deployments().inNamespace(NS).withName(d.name).get();
      if (resource != null)
        check(d, resource);
      return resource;
    } catch (KubernetesClientException e) {
      throw new ApiException(502, "Kubernetes lookup failed");
    }
  }
  public void update(com.devsphere.deployment.entity.Deployment d, String image, int replicas) {
    var resource = read(d);
    if (resource == null)
      throw new ApiException(409, "Kubernetes Deployment no longer exists");
    var containers = resource.getSpec().getTemplate().getSpec().getContainers();
    int index = -1;
    for (int i = 0; i < containers.size(); i++)
      if ("application".equals(containers.get(i).getName()))
        index = i;
    if (index < 0)
      throw new ApiException(409, "Application container missing");
    // RFC 6902 changes preserve security settings, resources, probes and all other containers.
    var body = List.of(Map.of("op", "test", "path", "/metadata/resourceVersion", "value",
                           resource.getMetadata().getResourceVersion()),
        Map.of("op", "replace", "path", "/spec/replicas", "value", replicas),
        Map.of("op", "replace", "path", "/spec/template/spec/containers/" + index + "/image",
            "value", image));
    try {
      client.apps().deployments().inNamespace(NS).withName(d.name).patch(
          PatchContext.of(PatchType.JSON), Serialization.asJson(body));
    } catch (KubernetesClientException e) {
      throw new ApiException(
          e.getCode() == 409 || e.getCode() == 422 ? 409 : 502, "Kubernetes update failed");
    }
  }
  public void delete(com.devsphere.deployment.entity.Deployment d) {
    try {
      var service = client.services().inNamespace(NS).withName(d.name).get();
      if (service != null)
        check(d, service);
      var deployment = read(d);
      // Resource-version preconditions prevent deletion of a replacement resource with the same
      // name.
      if (service != null)
        client.services().inNamespace(NS).resource(service).lockResourceVersion().delete();
      if (deployment != null)
        client.apps()
            .deployments()
            .inNamespace(NS)
            .resource(deployment)
            .lockResourceVersion()
            .delete();
    } catch (KubernetesClientException e) {
      throw new ApiException(502, "Kubernetes deletion failed; retry is safe");
    }
  }
  public List<Pod> pods(com.devsphere.deployment.entity.Deployment d) {
    read(d);
    try {
      return client.pods().inNamespace(NS).withLabels(labels(d)).list().getItems();
    } catch (KubernetesClientException e) {
      throw new ApiException(502, "Kubernetes pod lookup failed");
    }
  }
  public String logs(com.devsphere.deployment.entity.Deployment d, int tail) {
    var pods = pods(d);
    if (pods.isEmpty())
      return "No pods found for this deployment.";
    try {
      String logs = client.pods()
                        .inNamespace(NS)
                        .withName(pods.getFirst().getMetadata().getName())
                        .inContainer("application")
                        .tailingLines(tail)
                        .getLog();
      return logs.substring(Math.max(0, logs.length() - 40000));
    } catch (KubernetesClientException e) {
      throw new ApiException(409, "Pod logs are not available yet");
    }
  }
  public void ready() {
    try {
      client.apps().deployments().inNamespace(NS).list(
          new ListOptionsBuilder().withLimit(1L).build());
    } catch (KubernetesClientException e) {
      throw new ApiException(503, "Kubernetes unavailable");
    }
  }
}
