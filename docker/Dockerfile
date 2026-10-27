ARG ALLOY_VERSION=v1.21.2
# Must match the snmp_exporter version embedded in ALLOY_VERSION (see Alloy's go.mod).
ARG SNMP_EXPORTER_VERSION=v0.29.0
ARG NET_SNMP_VERSION=v5.9.4

# Alloy's prometheus.exporter.snmp doesn't read MIBs at runtime; it needs a
# snmp_exporter module file. Render one from the QNAP MIBs at build time.
FROM golang:1.24-bookworm AS snmp-generator

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

FROM grafana/alloy:${ALLOY_VERSION}

ARG ALLOY_VERSION
ARG TARGETPLATFORM
ARG BUILD_DATE
ARG REVISION
ARG VERSION
ARG REF

ENV ALLOY_VERSION=${ALLOY_VERSION}
ENV TARGETPLATFORM=${TARGETPLATFORM}
ENV BUILD_DATE=${BUILD_DATE}
ENV REVISION=${REVISION}
ENV VERSION=${VERSION}
ENV REF=${REF}

LABEL org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.authors="bartosz.sosnowski" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.url="https://github.com/bsosnowski/qnap-exporter" \
      org.opencontainers.image.documentation="https://github.com/bsosnowski/qnap-exporter/blob/main/README.md" \
      org.opencontainers.image.source="https://raw.githubusercontent.com/bsosnowski/qnap-exporter/refs/heads/main/docker/Dockerfile" \
      org.opencontainers.image.revision="${REVISION}" \
      org.opencontainers.image.ref.name="${REF}" \
      org.opencontainers.image.title="Qnap Exporter" \
      org.opencontainers.image.description="SNMP Qnap Exporter" \
      arch="${TARGETPLATFORM}" \
      alloy.version="${ALLOY_VERSION}"

COPY --from=snmp-generator /generator/snmp.yml /etc/alloy/snmp.yml
COPY config.alloy /etc/alloy/config.alloy

# Alloy UI and health endpoint (/-/ready).
EXPOSE 12345

ENTRYPOINT ["/bin/alloy"]
CMD ["run", "/etc/alloy/config.alloy", "--storage.path=/var/lib/alloy/data", "--server.http.listen-addr=0.0.0.0:12345"]
