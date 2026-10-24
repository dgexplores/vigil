# Native ARM build of the attributed Bank of Anthos Java services.
FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /src
COPY . .
RUN mvn -B -ntp -DskipTests package
FROM eclipse-temurin:17-jre
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=build /src/target/*.jar /app/service.jar
ENV JAVA_TOOL_OPTIONS="-Xms64m -Xmx256m"
USER 1000:1000
ENTRYPOINT ["java", "-jar", "/app/service.jar"]
