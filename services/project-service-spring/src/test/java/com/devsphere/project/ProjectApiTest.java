package com.devsphere.project;
import static org.junit.jupiter.api.Assertions.*;

import com.sun.net.httpserver.HttpServer;
import java.net.*;
import java.net.http.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.junit.jupiter.api.*;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import tools.jackson.databind.json.JsonMapper;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class ProjectApiTest {
  @org.springframework.beans.factory.annotation.Autowired
  com.devsphere.project.repository.ProjectRepository repository;
  @BeforeEach
  void clearDatabase() {
    repository.deleteAll();
  }
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
    r.add("spring.datasource.url", () -> "jdbc:h2:mem:projects;MODE=PostgreSQL;DB_CLOSE_DELAY=-1");
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

  Map<String, Object> payload() {
    return new HashMap<>(
        Map.of("name", "Demo", "slug", "demo-" + UUID.randomUUID().toString().substring(0, 8),
            "description", "University practical", "templateId", "fastapi-basic"));
  }
  String create() throws Exception {
    var result = call("POST", "/projects", payload(), "owner");
    assertEquals(201, result.statusCode(), result.body());
    return String.valueOf(data(result).get("id"));
  }
  @Test
  void createUsesAuthenticatedOwner() throws Exception {
    var result = call("POST", "/projects", payload(), "owner");
    assertEquals(201, result.statusCode(), result.body());
    assertEquals(OWNER, data(result).get("ownerId"));
    assertEquals("draft", data(result).get("status"));
  }
  @Test
  void readProject() throws Exception {
    String id = create();
    assertEquals(id, data(call("GET", "/projects/" + id, null, "owner")).get("id"));
  }
  @Test
  void listOwnProjects() throws Exception {
    create();
    var result = call("GET", "/projects", null, "owner");
    assertEquals(200, result.statusCode());
    assertFalse(JSON.readValue(result.body(), List.class).isEmpty());
    assertEquals("[]", call("GET", "/projects", null, "other").body());
  }
  @Test
  void updateMetadata() throws Exception {
    String id = create();
    var body = payload();
    body.put("name", "Edited");
    assertEquals(200, call("PUT", "/projects/" + id, body, "owner").statusCode());
    assertEquals("Edited", data(call("GET", "/projects/" + id, null, "owner")).get("name"));
  }
  @Test
  void deleteProject() throws Exception {
    String id = create();
    assertEquals(204, call("DELETE", "/projects/" + id, null, "owner").statusCode());
    assertEquals(404, call("GET", "/projects/" + id, null, "owner").statusCode());
  }
  @Test
  void duplicateOwnerSlugConflicts() throws Exception {
    var body = payload();
    assertEquals(201, call("POST", "/projects", body, "owner").statusCode());
    assertEquals(409, call("POST", "/projects", body, "owner").statusCode());
    assertEquals(201, call("POST", "/projects", body, "other").statusCode());
  }
  @Test
  void invalidSlugRejected() throws Exception {
    var body = payload();
    body.put("slug", "Upper_Case");
    assertEquals(400, call("POST", "/projects", body, "owner").statusCode());
  }
  @Test
  void missingAuthenticationRejected() throws Exception {
    assertEquals(401, call("GET", "/projects", null, null).statusCode());
    assertEquals(401, call("GET", "/projects", null, "invalid").statusCode());
  }
  @Test
  void crossUserReadUpdateDeleteHidden() throws Exception {
    String id = create();
    for (String method : List.of("GET", "PUT", "DELETE"))
      assertEquals(404,
          call(method, "/projects/" + id, method.equals("PUT") ? payload() : null, "other")
              .statusCode());
  }
  @Test
  void clientCannotAssignOwner() throws Exception {
    var body = payload();
    body.put("ownerId", OTHER);
    assertEquals(400, call("POST", "/projects", body, "owner").statusCode());
  }
  @Test
  void provisioningIsNotFabricated() throws Exception {
    String id = create();
    assertNull(data(call("GET", "/projects/" + id, null, "owner")).get("provisioningOperationId"));
  }
}
