#!/usr/bin/env python
import sqlite3
from sentence_transformers import SentenceTransformer
from kubernetes import client, config
from kubernetes.client import CustomObjectsApi
import os
import time
from dotenv import load_dotenv
from prometheus_client import start_http_server, Gauge, REGISTRY, CollectorRegistry
import threading
import socket

# Load environment variables
load_dotenv()

# Set API keys & configurations
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_ENDPOINT = os.getenv("GROQ_ENDPOINT")
USE_GROQ = os.getenv("USE_GROQ", "False").lower() == "true"  # Toggle AI calls
ANOMALY_THRESHOLD = int(os.getenv("ANOMALY_THRESHOLD", 3))  # Threshold for anomaly alerts
# SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL") if os.getenv("SLACK_ENABLED", "False").lower() == "true" else None

# if os.getenv("SLACK_ENABLED", "False").lower() == "true" and not os.getenv("SLACK_WEBHOOK_URL"):
#     raise ValueError("SLACK_WEBHOOK_URL is required for Slack notifications.")

# if os.getenv("SLACK_ENABLED").lower() == "true":
#     SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
# else:
#     SLACK_WEBHOOK_URL = None

# Global registry for Prometheus metrics
registry = CollectorRegistry()

# Check if port 8090 is already in use
def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0  # Returns True if port is in use

# Start Prometheus server **only if not already running**
def start_metrics_server():
    if os.getenv("METRICS_SERVER", "False").lower() == "true":
        try:
            if is_port_in_use(8090):
                print("✅ Prometheus server is already running on port 8090. Skipping restart.")
            else:
                print("🚀 Starting Prometheus server on port 8090...")
                start_http_server(8090)  # Start the server only if it's not already running
        except BrokenPipeError:
            print("⚠️ Warning: Broken pipe detected. Restarting Prometheus server...")
            os.system("fuser -k 8090/tcp")  # Kill any process using port 8090
            start_http_server(8090)  # Restart Prometheus server

# Run Prometheus server in a background thread
if "prometheus_thread" not in globals():
    prometheus_thread = threading.Thread(target=start_metrics_server, daemon=True)
    prometheus_thread.start()

# Register metrics **only if not already registered**
if "log_count_metric" not in globals():
    anomaly_metric = Gauge("kubernetes_anomalies", "Number of detected anomalies", registry=registry)
    error_log_metric = Gauge("kubernetes_error_logs", "Total number of error logs", registry=registry)
    log_count_metric = Gauge("kubernetes_log_count", "Total number of logs processed", registry=registry)
    memory_usage = Gauge("pod_mem_kb", "memory usage of pod", registry=registry)


# Load Kubernetes configuration
config.load_kube_config(config_file="/Users/surabhi.kumar/go/src/github.com/stackrox/stackrox3/kube")
v1 = client.CoreV1Api()
custom_api = CustomObjectsApi()

# Load Sentence Transformer Model
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

# SQLite Database Setup
DB_FILE = "k8s_logs.db"


def get_pod_metrics():
    try:
        # Get all pods
        pods = v1.list_pod_for_all_namespaces()

        # Get metrics for all pods
        metrics = custom_api.list_cluster_custom_object(
            group="metrics.k8s.io",
            version="v1beta1",
            plural="pods"
        )

        # Process and print the metrics
        for pod in pods.items:
            pod_name = pod.metadata.name
            namespace = pod.metadata.namespace

            # Find matching metrics
            pod_metrics = next((item for item in metrics['items'] if
                                item['metadata']['name'] == pod_name and item['metadata']['namespace'] == namespace),
                               None)

            if pod_metrics:
                #print(f"Pod: {pod_name} (Namespace: {namespace})")
                for container in pod_metrics['containers']:
                    container_name = container['name']
                    cpu = container['usage']['cpu']
                    memory = container['usage']['memory']
                    conn = sqlite3.connect(DB_FILE)
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO memory (pod, namespace, memory, cpuhz, timestamp) VALUES (?,?, ?, ?, ?)",
                                           (container_name, namespace, memory, cpu, pod_metrics["timestamp"]))
                    conn.commit()
                    conn.close()


                #print("%s %s %s",container_name,cpu,memory)
            else:
                print(f"No metrics found for pod: {pod_name} in namespace: {namespace}")
                print("---")

    except Exception as e:
        print(f"An error occurred: {e}")

while True:
  get_pod_metrics()
  time.sleep(5)
