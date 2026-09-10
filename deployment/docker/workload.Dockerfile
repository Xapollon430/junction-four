FROM python:3.11-slim-bookworm

COPY requirements.txt /workload/requirements.txt
RUN pip install --no-cache-dir -r /workload/requirements.txt
COPY deployment/workload /workload
COPY deployment/tests /opt/antithesis/test/v1

RUN chmod +x /workload/wait_for_cluster.py /opt/antithesis/test/v1/traffic/*.py \
    && mkdir -p /opt/antithesis/catalog \
    && ln -s /opt/antithesis/test/v1 /opt/antithesis/catalog/workload-tests

ENTRYPOINT ["python", "/workload/wait_for_cluster.py"]
