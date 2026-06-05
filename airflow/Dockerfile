FROM apache/airflow:2.9.3

USER root
RUN mkdir -p /opt/airflow-metadata && chown -R airflow:root /opt/airflow-metadata
USER airflow

RUN pip install --no-cache-dir dbt-core==1.8.3 dbt-postgres==1.8.2
