package com.devsphere.deployment;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

import com.devsphere.common.ApiException;
import com.devsphere.deployment.discovery.ProjectDiscovery;
import com.devsphere.deployment.entity.Deployment;
import com.devsphere.deployment.kubernetes.Workloads;
import com.devsphere.deployment.repository.DeploymentRepository;
import com.sun.net.httpserver.HttpServer;
import java.net.*;
import java.net.http.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import tools.jackson.databind.json.JsonMapper;
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
    properties = "devsphere.deployment-writes=true")
class DeploymentApiTest {
  static final String OWNER = "11111111-1111-4111-8111-111111111111";
  static final String OTHER = "22222222-2222-4222-8222-222222222222";
  static final JsonMapper JSON = new JsonMapper();
  static final HttpServer AUTH;
  static {
    try {
      AUTH = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
      AUTH.createContext("/auth/me", e -> {
        String token = e.getRequestHeaders().getFirst("Authorization");
        boolean invalid = "Bearer invalid".equals(token);
        String id = "Bearer other".equals(token) ? OTHER : OWNER;
        byte[] body =
            (invalid ? "{\"detail\":\"Invalid token\"}"
                     : "{\"id\":\"" + id + "\",\"role\":\"developer\",\"is_active\":true}")
                .getBytes(StandardCharsets.UTF_8);
        e.getResponseHeaders().set("Content-Type", "application/json");
        e.sendResponseHeaders(invalid ? 401 : 200, body.length);
        e.getResponseBody().write(body);
        e.close();
      });
      AUTH.start();
    } catch (Exception e) {
      throw new ExceptionInInitializerError(e);
    }
  }
  @LocalServerPort int port;
  @DynamicPropertySource
  static void properties(DynamicPropertyRegistry r) {
    r.add("devsphere.auth-url", () -> "http://127.0.0.1:" + AUTH.getAddress().getPort());
    r.add(
        "spring.datasource.url", () -> "jdbc:h2:mem:deployments;MODE=PostgreSQL;DB_CLOSE_DELAY=-1");
    r.add("spring.datasource.username", () -> "sa");
    r.add("spring.datasource.password", () -> "");
    r.add("spring.jpa.hibernate.ddl-auto", () -> "create-drop");
    r.add("spring.flyway.enabled", () -> "false");
    r.add("eureka.client.enabled", () -> "false");
  }
  HttpResponse<String> call(String method, String path, Object body, String token)
      throws Exception {
    var builder = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + path))
                      .header("Content-Type", "application/json");
    if (token != null)
      builder.header("Authorization", "Bearer " + token);
    builder.method(method,
        body == null ? HttpRequest.BodyPublishers.noBody()
                     : HttpRequest.BodyPublishers.ofString(JSON.writeValueAsString(body)));
    return HttpClient.newHttpClient().send(builder.build(), HttpResponse.BodyHandlers.ofString());
  }
  Map<?, ?> data(HttpResponse<String> response) {
    return JSON.readValue(response.body(), Map.class);
  }
  @AfterAll
  static void stopAuth() {
    AUTH.stop(0);
  }

  @MockitoBean Workloads workloads;
  @MockitoBean ProjectDiscovery discovery;
  @Autowired DeploymentRepository repository;
  static final String IMAGE = "nginxinc/nginx-unprivileged:stable-alpine";
  Map<String, Object> payload() {
    return new HashMap<>(Map.of("name", "demo-api", "image", IMAGE, "replicas", 1, "container_port",
        8080, "project_id", UUID.randomUUID().toString()));
  }
  String create() throws Exception {
    var result = call("POST", "/deployments", payload(), "owner");
    assertEquals(201, result.statusCode(), result.body());
    return String.valueOf(data(result).get("id"));
  }
  @Test
  void createInvokesProjectLookupAndKubernetes() throws Exception {
    String id = create();
    assertEquals("java", repository.findById(id).orElseThrow().managementService);
    verify(discovery).verify(any(), any(), eq("Bearer owner"));
    verify(workloads).create(any());
  }
  @Test
  void readAndListOwned() throws Exception {
    String id = create();
    assertEquals(200, call("GET", "/deployments/" + id, null, "owner").statusCode());
    assertEquals(200, call("GET", "/deployments", null, "owner").statusCode());
    assertEquals("[]", call("GET", "/deployments", null, "other").body());
  }
  @Test
  void updateScaleAndRollbackProduceHistory() throws Exception {
    String id = create();
    assertEquals(
        200, call("PUT", "/deployments/" + id, Map.of("replicas", 2), "owner").statusCode());
    assertEquals(2, repository.findById(id).orElseThrow().replicas);
    verify(workloads).update(any(), eq(IMAGE), eq(2));
    assertEquals(200,
        call("POST", "/deployments/" + id + "/rollback", Map.of("revision", 1), "owner")
            .statusCode());
    assertEquals(1, repository.findById(id).orElseThrow().replicas);
    assertEquals(3,
        JSON.readValue(
                call("GET", "/deployments/" + id + "/revisions", null, "owner").body(), List.class)
            .size());
  }
  @Test
  void updateAllowlistedImage() throws Exception {
    String id = create();
    String image = "devsphere-built/demo-api:abcdef12";
    assertEquals(
        200, call("PATCH", "/deployments/" + id, Map.of("image", image), "owner").statusCode());
    assertEquals(image, repository.findById(id).orElseThrow().image);
  }
  @Test
  void deletionSoftDeletesAfterKubernetes() throws Exception {
    String id = create();
    assertEquals(200, call("DELETE", "/deployments/" + id, null, "owner").statusCode());
    assertEquals("deleted", repository.findById(id).orElseThrow().status);
    verify(workloads).delete(any());
  }
  @Test
  void invalidImageDoesNotReachKubernetes() throws Exception {
    var body = payload();
    body.put("image", "ubuntu:latest");
    assertEquals(422, call("POST", "/deployments", body, "owner").statusCode());
    verify(workloads, never()).create(any());
  }
  @Test
  void unauthorizedAndCrossUserRejected() throws Exception {
    assertEquals(401, call("GET", "/deployments", null, null).statusCode());
    String id = create();
    for (String method : List.of("GET", "DELETE", "PUT"))
      assertEquals(404,
          call(method, "/deployments/" + id, method.equals("PUT") ? Map.of("replicas", 2) : null,
              "other")
              .statusCode());
  }
  @Test
  void kubernetesFailurePersistsFailedAudit() throws Exception {
    doThrow(new ApiException(502, "Unavailable")).when(workloads).create(any());
    assertEquals(502, call("POST", "/deployments", payload(), "owner").statusCode());
    assertTrue(repository.findAll().stream().anyMatch(d -> "failed".equals(d.status)));
  }
  @Test
  void projectFailurePreventsResourceCreation() throws Exception {
    when(discovery.verify(any(), any(), any()))
        .thenThrow(new ApiException(503, "Discovery unavailable"));
    assertEquals(503, call("POST", "/deployments", payload(), "owner").statusCode());
    verify(workloads, never()).create(any());
  }
  @Test
  void legacyRecordsReadableButCannotBeMutated() throws Exception {
    String id = create();
    var d = repository.findById(id).orElseThrow();
    d.managementService = "python";
    d.name = "ds-legacy";
    repository.saveAndFlush(d);
    assertEquals(200, call("GET", "/deployments/" + id, null, "owner").statusCode());
    assertEquals(
        409, call("PUT", "/deployments/" + id, Map.of("replicas", 2), "owner").statusCode());
    assertEquals(409, call("DELETE", "/deployments/" + id, null, "owner").statusCode());
  }
  @Test
  void invalidReplicasAndUnknownRevisionRejected() throws Exception {
    String id = create();
    assertEquals(
        400, call("PUT", "/deployments/" + id, Map.of("replicas", 3), "owner").statusCode());
    assertEquals(404,
        call("POST", "/deployments/" + id + "/rollback", Map.of("revision", 99), "owner")
            .statusCode());
  }
}
