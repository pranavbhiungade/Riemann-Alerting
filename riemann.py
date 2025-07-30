import subprocess  # run commands remotely
import time 
from riemann_client.transport import TCPTransport
from riemann_client.client import Client
from riemann_client.riemann_pb2 import Event, Attribute
# components of riemann_client

# Configuration
RIEMANN_HOST = "192.168.64.11"       # Riemann VM IP
RIEMANN_PORT = 5555
NGINX_VM = "salt-minion-3"
NGINX_LOG_PATH = "/var/log/nginx/grafana_access.log"
LOG_COMMAND = ["multipass", "exec", NGINX_VM, "--", "tail", "-F", NGINX_LOG_PATH]

# log parse function
def extract_method_response(line):
    try:
        parts = line.strip().split()  # remove lead/trailing whitespaces and splits the line using whitespaces
        method = parts[5].strip('"')  # GET/POST (at index number 5)
        code = int(parts[8])          # response status code (at index number 8)
        return method, code
    except Exception as e:
        print(f"[!] Failed to parse line: {line.strip()} | Error: {e}")
        return None, None

def main():
    # Connect to Riemann
    try:
        transport = TCPTransport(host=RIEMANN_HOST, port=RIEMANN_PORT)
        transport.connect()
        client = Client(transport)
        print(f"Connected to Riemann at {RIEMANN_HOST}:{RIEMANN_PORT}")
    except Exception as e:
        print(f"Failed to connect to Riemann: {e}")
        return

    # Start tailing the log file on the remote VM
    process = subprocess.Popen(LOG_COMMAND, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    try:
        for line in process.stdout:
            method, code = extract_method_response(line)
            if method and code:
                try:
                    # Send events to reimann
                    event = Event(
                        host=NGINX_VM,
                        service=f"nginx {method} requests",
                        state="ok" if 200 <= code < 300 else "error",
                        description=f"Method {method} got response code {code}",
                        ttl=30,
                        time=int(time.time()),
                        metric_sint64=1  # Required for numeric metric
                    )
                    event.attributes.extend([
                        Attribute(key="response_code", value=str(code)),
                        Attribute(key="method", value=method)
                    ])
                    client.send_event(event)
                    print(f"Sent: {event.description}")
                except Exception as send_error:
                    print(f"[!] Send failed: {send_error}")
    except KeyboardInterrupt:
        print("[x] Interrupted by user. Exiting...")
    finally:
        process.kill()
        transport.disconnect()

if __name__ == "__main__":
    main()

