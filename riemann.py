import subprocess
from riemann_client.transport import TCPTransport
from riemann_client.client import Client
from riemann_client.riemann_pb2 import Event
import re
import threading

RIEMANN_HOST = "192.168.64.11"
RIEMANN_PORT = 5555

LOG_FILES = {
    "grafana_access": "/var/log/nginx/grafana_access.log",
    "docker_access": "/var/log/nginx/docker_access.log",
    "grafana_error": "/var/log/nginx/grafana_error.log",
    "docker_error": "/var/log/nginx/docker_error.log"
}

def extract_fields(line):
    try:
        # Regex for common nginx access log format
        # Example: 192.168.64.1 - - [31/Jul/2025:11:27:29 +0530] "GET /login HTTP/1.1" 200 52958 "-" "python-requests/2.32.4" rt=0.005 ut=0.006
        match = re.match(r'^(\S+) .*?"(\S+)\s(\S+).*?" (\d{3}) .*?"[^"]*" "([^"]*)"', line)
        if match:
            ip = match.group(1)
            method = match.group(2)
            path = match.group(3)
            code = int(match.group(4))
            user_agent = match.group(5)
            return method, code, ip, path, user_agent
    except Exception as e:
        print(f"[!] Failed to parse line: {line.strip()} | Error: {e}")
    return None, None, None, None, None

def process_log(log_name, file_path):
    command = ["multipass", "exec", "salt-minion-3", "--", "tail", "-F", file_path]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    try:
        transport = TCPTransport(host=RIEMANN_HOST, port=RIEMANN_PORT)
        transport.connect()
        client = Client(transport)
        print(f"[✓] Connected to Riemann for {log_name}")

        for line in process.stdout:
            method, code, ip, path, user_agent = extract_fields(line)
            if method and code and ip:
                try:
                    # Send method & code metric
                    event_method = Event(
                        host=log_name,
                        service=f"{log_name} - {method} requests",
                        metric_f=code,
                        state="ok" if 200 <= code < 300 else "error",
                        description=f"{log_name} - Method {method} got response code {code}",
                        ttl=30
                    )
                    client.send_event(event_method)

                    # Send IP metric (e.g., we log code 1 for presence)
                    event_ip = Event(
                        host=log_name,
                        service=f"{log_name} - IP {ip}",
                        metric_f=1,
                        state="ok",
                        description=f"{log_name} - Request from IP {ip}",
                        ttl=30
                    )
                    client.send_event(event_ip)

                    # Send Path
                    event_path = Event(
                        host=log_name,
                        service=f"{log_name} - Path {path}",
                        metric_f=1,
                        state="ok",
                        description=f"{log_name} - Accessed path {path}",
                        ttl=30
                    )
                    client.send_event(event_path)

                    # Send User-Agent
                    event_ua = Event(
                        host=log_name,
                        service=f"{log_name} - UserAgent {user_agent}",
                        metric_f=1,
                        state="ok",
                        description=f"{log_name} - User-Agent {user_agent}",
                        ttl=30
                    )
                    client.send_event(event_ua)

                    print(f"[✓] Sent from {log_name}: {method} {code} {ip} {path} {user_agent}")

                except Exception as send_error:
                    print(f"[!] Send failed for {log_name}: {send_error}")

    except Exception as e:
        print(f"[!] Failed to connect to Riemann for {log_name}: {e}")

def main():
    threads = []
    for log_name, file_path in LOG_FILES.items():
        t = threading.Thread(target=process_log, args=(log_name, file_path))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

if __name__ == "__main__":
    main()

