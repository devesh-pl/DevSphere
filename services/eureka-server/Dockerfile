FROM maven:3.9.11-eclipse-temurin-21 AS build
ENV MAVEN_OPTS="-Xmx384m -XX:+UseSerialGC"
WORKDIR /workspace
COPY pom.xml .
COPY services/java-common services/java-common
COPY services/eureka-server services/eureka-server
COPY services/project-service-spring services/project-service-spring
COPY services/deployment-service-spring services/deployment-service-spring
RUN --mount=type=cache,id=devsphere-maven,target=/root/.m2,sharing=locked mvn -B -pl services/eureka-server -am package -DskipTests
FROM eclipse-temurin:21-jre-alpine
RUN addgroup -S devsphere && adduser -S devsphere -G devsphere && apk add --no-cache curl
WORKDIR /app
COPY --from=build /workspace/services/eureka-server/target/eureka-server-0.2.0-SNAPSHOT.jar /app/service.jar
USER devsphere
ENV JAVA_TOOL_OPTIONS="-Xms48m -Xmx192m -XX:MaxMetaspaceSize=160m -XX:+UseSerialGC"
EXPOSE 8761
HEALTHCHECK --interval=15s --start-period=180s --timeout=5s CMD curl -fsS http://localhost:8761/actuator/health || exit 1
ENTRYPOINT ["java","-jar","/app/service.jar"]
