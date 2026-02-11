# Use Ubuntu as base image
FROM ubuntu:22.04

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Update and install in separate steps for better error handling
RUN apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get update --fix-missing && \
    apt-get install -y --no-install-recommends \
    bash \
    coreutils \
    findutils \
    grep \
    sed \
    gawk \
    curl \
    wget \
    git \
    vim \
    nano \
    tar \
    gzip \
    unzip \
    ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Create working directory
WORKDIR /workspace

# Default command
CMD ["/bin/bash"]