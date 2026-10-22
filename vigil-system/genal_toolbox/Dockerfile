# Reuse the upstream Go server at a fixed version rather than building moving main.
FROM us-central1-docker.pkg.dev/database-toolbox/toolbox/toolbox:0.16.0
WORKDIR /app
COPY --chown=nonroot tools.yaml /app/tools.yaml
ENTRYPOINT ["/toolbox"]
CMD ["--tools-file", "/app/tools.yaml", "--address", "0.0.0.0"]
