# Use the official Golang image to create a build artifact.
# This is the "builder" stage.
FROM golang:1.22-alpine as builder

# Install git
RUN apk add --no-cache git

# Set the Current Working Directory inside the container
WORKDIR /app

# Clone the genai-toolbox repository
RUN git clone https://github.com/googleapis/genai-toolbox .

# Build the Go app
# -o /app/genal-toolbox: output the binary to /app/genal-toolbox
# CGO_ENABLED=0: disable CGO for a statically linked binary
# GOOS=linux: build for Linux
RUN CGO_ENABLED=0 GOOS=linux go build -o /app/genal-toolbox .

# Use a minimal image for the final stage
# This is the "runner" stage.
FROM gcr.io/distroless/base-debian11

# Set the Current Working Directory inside the container
WORKDIR /app

# Copy the binary from the builder stage
COPY --from=builder /app/genal-toolbox .

# Copy the tools.yaml file
# This file is expected to be in the build context.
COPY tools.yaml .

# The command to run the application
# The actual command might be different, this is a placeholder
CMD ["/app/genal-toolbox", "--config_file", "/app/tools.yaml"]
