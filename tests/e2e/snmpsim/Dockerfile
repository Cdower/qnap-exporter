# Simulated QNAP SNMP agent for the end-to-end test. It answers SNMP v2c
# requests from the .snmprec files in data/; each file's basename is the
# community it answers to.
FROM python:3.13-slim

# snmpsim 1.2.2 imports pysmi without declaring it as a dependency.
RUN pip install --no-cache-dir snmpsim==1.2.2 pysmi==2.0.0

COPY data/ /usr/local/snmpsim/data/

# snmpsim refuses to run as root.
USER nobody

EXPOSE 1161/udp

ENTRYPOINT ["snmpsim-command-responder", "--data-dir=/usr/local/snmpsim/data", "--agent-udpv4-endpoint=0.0.0.0:1161", "--cache-dir=/tmp/snmpsim"]
