package com.devsphere.project;
import static org.junit.jupiter.api.Assertions.*;

import com.devsphere.common.*;
import com.devsphere.project.dto.ProjectRequest;
import com.devsphere.project.service.ProvisioningClient;
import com.sun.net.httpserver.HttpServer;
import java.net.*;
import java.util.*;
import org.junit.jupiter.api.Test;
class ProvisioningClientTest {
  @Test
  void verifiesActualCompletedResultAndRejectsMismatch() throws Exception {
    var server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
    var user = new AuthUser(UUID.randomUUID(), "developer");
    var op = UUID.randomUUID();
    server.createContext("/operations/", e -> {
      String result = "{\"project_slug\":\"demo-api\",\"template_id\":\"fastapi-basic\"}";
      var mapper = new tools.jackson.databind.json.JsonMapper();
      var body = mapper.writeValueAsBytes(Map.of("owner_id", user.id().toString(), "operation_type",
          "provision_project", "status", "completed", "result", result));
      e.getResponseHeaders().set("Content-Type", "application/json");
      e.sendResponseHeaders(200, body.length);
      e.getResponseBody().write(body);
      e.close();
    });
    server.start();
    try {
      var client = new ProvisioningClient("http://127.0.0.1:" + server.getAddress().getPort());
      assertEquals("provisioned",
          client.verify(new ProjectRequest("Demo", "demo-api", "", "fastapi-basic", op), user,
              "Bearer token"));
      assertEquals(409,
          assertThrows(ApiException.class,
              ()
                  -> client.verify(
                      new ProjectRequest("Demo", "wrong-slug", "", "fastapi-basic", op), user,
                      "Bearer token"))
              .status.value());
      assertEquals(404,
          assertThrows(ApiException.class,
              ()
                  -> client.verify(new ProjectRequest("Demo", "demo-api", "", "fastapi-basic", op),
                      new AuthUser(UUID.randomUUID(), "developer"), "Bearer token"))
              .status.value());
    } finally {
      server.stop(0);
    }
  }
}
