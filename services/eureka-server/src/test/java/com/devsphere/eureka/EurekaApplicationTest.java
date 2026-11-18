package com.devsphere.eureka;
import static org.junit.jupiter.api.Assertions.*;

import java.net.*;
import java.net.http.*;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class EurekaApplicationTest {
  @LocalServerPort int port;
  @Test
  void realServerExposesDashboardRegistryAndHealth() throws Exception {
    for (String path : new String[] {"/", "/eureka/apps", "/actuator/health"}) {
      var request = HttpRequest.newBuilder(URI.create("http://localhost:" + port + path))
                        .header("Accept", path.equals("/") ? "text/html" : "application/json")
                        .build();
      assertEquals(200,
          HttpClient.newHttpClient()
              .send(request, HttpResponse.BodyHandlers.ofString())
              .statusCode());
    }
  }
}
