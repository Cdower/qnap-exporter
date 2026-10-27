build:
		DOCKER_BUILDKIT=1 docker buildx build \
		--platform linux/amd64,linux/arm64 \
		--build-arg ALLOY_VERSION=v1.21.2 \
		--build-arg VERSION=9.9.9 \
		-t qnap-exporter:9.9.9 \
		--output="type=image" \
		--no-cache \
		--load \
		.