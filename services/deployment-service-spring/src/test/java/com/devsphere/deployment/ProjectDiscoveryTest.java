package com.devsphere.deployment;

import static org.junit.jupiter.api.Assertions.*;

import com.devsphere.common.*;
import com.devsphere.deployment.discovery.ProjectDiscovery;
import com.devsphere.deployment.kubernetes.Workloads;
import com.sun.net.httpserver.HttpServer;
import java.net.*;
import java.util.*;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class ProjectDiscoveryTest {
  static final UUID OWNER = UUID.randomUUID(), PROJECT = UUID.randomUUID();
  static final HttpServer SERVER;
  static {
    try {
      SERVER = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
      SERVER.createContext("/projects/", e -> {
        String header = e.getRequestHeaders().getFirst("Authorization");
        int status = header.equals("Bearer unavailable") ? 503
            : header.equals("Bearer other")
                || !e.getRequestURI().getPath().endsWith(PROJECT.toString())
            ? 404
            : 200;
        var mapper = new tools.jackson.databind.json.JsonMapper();
        byte[] body =
            mapper.writeValueAsBytes(status == 200 ? Map.of("id", PROJECT, "ownerId", OWNER)
                                                   : Map.of("detail", "Unavailable or not owned"));
        e.getResponseHeaders().set("Content-Type", "application/json");
        e.sendResponseHeaders(status, body.length);
        e.getResponseBody().write(body);
        e.close();
      });
      SERVER.start();
    } catch (Exception e) {
      throw new ExceptionInInitializerError(e);
    }
  }
  @DynamicPropertySource
  static void properties(DynamicPropertyRegistry r) {
    r.add("spring.datasource.url", () -> "jdbc:h2:mem:discovery;MODE=PostgreSQL;DB_CLOSE_DELAY=-1");
    r.add("spring.datasource.username", () -> "sa");
    r.add("spring.datasource.password", () -> "");
    r.add("spring.jpa.hibernate.ddl-auto", () -> "create-drop");
    r.add("spring.flyway.enabled", () -> "false");
    r.add("eureka.client.enabled", () -> "false");
    // Test-only simple discovery supplies an instance; the client still calls the logical service
    // name.
    r.add("spring.cloud.discovery.client.simple.instances.PROJECT-SERVICE[0].uri",
        () -> "http://127.0.0.1:" + SERVER.getAddress().getPort());
  }
  @MockitoBean Workloads workloads;
  @Autowired ProjectDiscovery discovery;
  @AfterAll
  static void stop() {
    SERVER.stop(0);
  }
  @Autowired org.springframework.web.client.RestClient.Builder infrastructureBuilder;
  @Test
  void infrastructureBootstrapUsesPlainDnsWithoutRegistry() {
    var result =
        infrastructureBuilder.build()
            .get()
            .uri("http://127.0.0.1:" + SERVER.getAddress().getPort() + "/projects/" + PROJECT)
            .header("Authorization", "Bearer owner")
            .retrieve()
            .body(Map.class);
    assertEquals(PROJECT.toString(), result.get("id"));
  }
  @Test
  void loadBalancerResolvesLogicalServiceAndForwardsAuthentication() {
    assertEquals(PROJECT.toString(),
        discovery.verify(PROJECT, new AuthUser(OWNER, "developer"), "Bearer owner").get("id"));
  }
  @Test
  void unknownAndCrossUserAreRejected() {
    assertEquals(404,
        assertThrows(ApiException.class,
            ()
                -> discovery.verify(
                    UUID.randomUUID(), new AuthUser(OWNER, "developer"), "Bearer owner"))
            .status.value());
    assertEquals(404,
        assertThrows(ApiException.class,
            ()
                -> discovery.verify(
                    PROJECT, new AuthUser(UUID.randomUUID(), "developer"), "Bearer other"))
            .status.value());
  }
  @Test
  void downstreamUnavailabilityIs503() {
    assertEquals(503,
        assertThrows(ApiException.class,
            () -> discovery.verify(PROJECT, new AuthUser(OWNER, "developer"), "Bearer unavailable"))
            .status.value());
  }
}
