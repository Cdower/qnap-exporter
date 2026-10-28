# Alloy embeds its own snmp_exporter (v0.29.0 as of Alloy v1.21.2). Newer
# generators are fine as long as the rendered snmp.yml only uses config fields
# that version understands.
ARG SNMP_EXPORTER_VERSION=v0.31.0
ARG NET_SNMP_VERSION=v5.9.4

# Alloy's prometheus.exporter.snmp doesn't read MIBs at runtime; it needs a
# snmp_exporter module file. Render one from the QNAP MIBs at build time.
# snmp.yml is platform-independent, so build it natively once instead of under
# emulation for every target platform.
FROM --platform=$BUILDPLATFORM golang:1.26-trixie AS snmp-generator

ARG SNMP_EXPORTER_VERSION
ARG NET_SNMP_VERSION

RUN apt-get update && \
    apt-get install --yes --no-install-recommends libsnmp-dev && \
    rm -rf /var/lib/apt/lists/*

RUN go install github.com/prometheus/snmp_exporter/generator@${SNMP_EXPORTER_VERSION}

WORKDIR /generator

# Base SMI definitions the QNAP MIBs import from.
RUN mkdir mibs && \
    for mib in SNMPv2-SMI SNMPv2-TC SNMPv2-CONF; do \
        curl -fsSL -o "mibs/${mib}.txt" \
            "https://raw.githubusercontent.com/net-snmp/net-snmp/${NET_SNMP_VERSION}/mibs/${mib}.txt"; \
    done

COPY NAS.mib QTS.mib mibs/
COPY snmp/generator.yml .

RUN MIBDIRS=/generator/mibs generator generate -g generator.yml -o snmp.yml

# Base images are pinned literally so Dependabot can track them.
FROM grafana/alloy:v1.21.2

ARG TARGETPLATFORM
ARG BUILD_DATE
ARG REVISION
ARG VERSION
ARG REF

ENV TARGETPLATFORM=${TARGETPLATFORM}
ENV BUILD_DATE=${BUILD_DATE}
ENV REVISION=${REVISION}
ENV VERSION=${VERSION}
ENV REF=${REF}

# alloy.version must match the grafana/alloy tag above; update both together.
LABEL org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.authors="cdower" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.url="https://github.com/cdower/qnap-exporter" \
      org.opencontainers.image.documentation="https://github.com/cdower/qnap-exporter/blob/main/README.md" \
      org.opencontainers.image.source="https://raw.githubusercontent.com/cdower/qnap-exporter/refs/heads/main/docker/Dockerfile" \
      org.opencontainers.image.revision="${REVISION}" \
      org.opencontainers.image.ref.name="${REF}" \
      org.opencontainers.image.title="Qnap Exporter" \
      org.opencontainers.image.description="SNMP Qnap Exporter" \
      arch="${TARGETPLATFORM}" \
      alloy.version="v1.21.2"

COPY --from=snmp-generator /generator/snmp.yml /etc/alloy/snmp.yml
COPY config.alloy /etc/alloy/config.alloy

# Alloy UI and health endpoint (/-/ready).
EXPOSE 12345

ENTRYPOINT ["/bin/alloy"]
CMD ["run", "/etc/alloy/config.alloy", "--storage.path=/var/lib/alloy/data", "--server.http.listen-addr=0.0.0.0:12345"]
