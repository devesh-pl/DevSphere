package com.devsphere.deployment;

import static org.junit.jupiter.api.Assertions.*;

import com.devsphere.common.ApiException;
import com.devsphere.deployment.entity.Deployment;
import com.devsphere.deployment.kubernetes.Workloads;
import io.fabric8.kubernetes.client.KubernetesClient;
import io.fabric8.kubernetes.client.server.mock.EnableKubernetesMockClient;
import java.util.Map;
import org.junit.jupiter.api.Test;

@EnableKubernetesMockClient(
    crud = true, kubernetesClientBuilderCustomizer = WorkloadsTest.ClientTimeouts.class)
class WorkloadsTest {
  // Cold TLS initialization needs a realistic timeout in CPU-limited test containers.
  public static class ClientTimeouts
      implements java.util.function.Consumer<io.fabric8.kubernetes.client.KubernetesClientBuilder> {
    public void accept(io.fabric8.kubernetes.client.KubernetesClientBuilder builder) {
      builder.editOrNewConfig().withConnectionTimeout(30000).withRequestTimeout(30000).endConfig();
      builder.withHttpClientFactory(
          new io.fabric8.kubernetes.client.jetty.JettyHttpClientFactory());
    }
  }
  KubernetesClient client;
  Deployment record() {
    var d = new Deployment();
    d.id = "11111111-1111-4111-8111-111111111111";
    d.name = "ds-java-11111111-111";
    d.ownerId = "22222222-2222-4222-8222-222222222222";
    d.namespace = Workloads.NS;
    d.image = "nginxinc/nginx-unprivileged:stable-alpine";
    d.containerPort = 8080;
    d.replicas = 1;
    return d;
  }
  @Test
  void realClientCreatesSecuredResourcesUpdatesAndDeletes() {
    var workloads = new Workloads(client);
    var d = record();
    workloads.create(d);
    var resource = workloads.read(d);
    var container = resource.getSpec().getTemplate().getSpec().getContainers().getFirst();
    assertTrue(container.getSecurityContext().getRunAsNonRoot());
    assertEquals(101L, container.getSecurityContext().getRunAsUser());
    assertFalse(container.getSecurityContext().getAllowPrivilegeEscalation());
    assertEquals("RuntimeDefault", container.getSecurityContext().getSeccompProfile().getType());
    assertEquals("128Mi", container.getResources().getLimits().get("memory").toString());
    assertFalse(resource.getSpec().getTemplate().getSpec().getAutomountServiceAccountToken());
    assertNotNull(client.services().inNamespace(Workloads.NS).withName(d.name).get());
    workloads.update(d, d.image, 2);
    assertEquals(2, workloads.read(d).getSpec().getReplicas());
    workloads.delete(d);
    assertNull(workloads.read(d));
    assertNull(client.services().inNamespace(Workloads.NS).withName(d.name).get());
  }
  @Test
  void mismatchedOwnershipPreventsMutationAndDeletion() {
    var workloads = new Workloads(client);
    var d = record();
    workloads.create(d);
    d.ownerId = "33333333-3333-4333-8333-333333333333";
    assertEquals(409,
        assertThrows(ApiException.class, () -> workloads.update(d, d.image, 2)).status.value());
    assertEquals(409, assertThrows(ApiException.class, () -> workloads.delete(d)).status.value());
    assertNotNull(client.apps().deployments().inNamespace(Workloads.NS).withName(d.name).get());
  }
}
