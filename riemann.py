import subprocess
from riemann_client.transport import TCPTransport
from riemann_client.client import Client
from riemann_client.riemann_pb2 import Event, Attribute
#from riemann_client.client import Event

RIEMANN_HOST = "192.168.64.11"
RIEMANN_PORT = 5555
LOG_COMMAND = ["multipass", "exec", "salt-minion-3", "--", "tail", "-F", "/var/log/nginx/grafana_access.log"]
TARGET_AGENT_PREFIX = "python-requests/"

def extract_log_details(line):
    try:
        parts = line.strip().split()
        ip = parts[0]
        method = parts[5].strip('"')
        path = parts[6]
        code = int(parts[8])
        user_agent = line.strip().split('"')[5]  # should be after second pair of quotes

        # Extract rt and ut if present
        rt = None
        ut = None
        if "rt=" in line:
            rt = line.split("rt=")[1].split()[0]
        if "ut=" in line:
            ut = line.split("ut=")[1].split()[0]
            

        return ip, method, path, code, user_agent, rt, ut
    except Exception as e:
        print(f"[!] Failed to parse line: {line.strip()} | Error: {e}")
        return None, None, None, None, None, None, None

def main():
    try:
        transport = TCPTransport(host=RIEMANN_HOST, port=RIEMANN_PORT)
        transport.connect()
        client = Client(transport)
        print(f"[✓] Connected to Riemann at {RIEMANN_HOST}:{RIEMANN_PORT}")
    except Exception as e:
        print(f"[!] Failed to connect to Riemann: {e}")
        return

    process = subprocess.Popen(LOG_COMMAND, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    try:
        for line in process.stdout:
            ip, method, path, code, user_agent, rt, ut = extract_log_details(line)

            if not user_agent.startswith(TARGET_AGENT_PREFIX):
                continue  # Skip non-python-requests agents

            if ip and method and path and code:
                state = "ok" if 200 <= code < 300 else "error"
                service_name = f"nginx {method} {code} from {ip}"
                description = f"{method} {path} from {ip} returned {code} rt={rt} and ut={ut}"

                attributes = [
                    Attribute(key="method", value=method),
                    Attribute(key="path", value=path),
                    Attribute(key="response_code", value=str(code)),
                    Attribute(key="agent", value=user_agent),
                    Attribute(key="ip", value=ip)
                ]

                if rt:
                    attributes.append(Attribute(key="rt", value=rt))
                if ut:
                    attributes.append(Attribute(key="ut", value=ut))

                event = Event(
                    host="salt-minion-3",
                    service=service_name,
                    metric_f=1.0,
                    state=state,
                    description=description,
                    ttl=60,
                    attributes=attributes
                )
                client.send_event(event)
                print(f"[✓] Sent: {description}")
    except KeyboardInterrupt:
        print("\n[!] Interrupted. Exiting...")

if __name__ == "__main__":
    main()

