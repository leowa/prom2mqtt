import json
import click
import socket
import time
import logging
from .helper import requests_retry_session
from prometheus_client.parser import text_string_to_metric_families as t2mf
from paho.mqtt.publish import multiple
from urllib.parse import urljoin


__version__ = "0.0.1"


@click.command()
@click.option("--prometheus", "-p", default="http://localhost:9090", help="prometheus server address")
@click.option("--mqtt", default="localhost:1883", help="mqtt server address")
@click.option("--topic", "-t", default="{job}/{metrics}/{instance}", help="topic name format string")
@click.option("--wait", "-w", default=5000, type=int, help="sleep ms for the next polling")
def main(prometheus, mqtt, topic, wait):
    host, port = mqtt.split(':')
    client_id = "prom2mqtt_" + socket.gethostname()
    LOG = logging.getLogger("prom2mqtt")
    logging.basicConfig(level=logging.INFO,
                        format='[%(asctime)s] %(levelname)s %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')

    session = requests_retry_session()
    targets_res = session.get(urljoin(prometheus, "api/v1/targets"))
    targets = []
    for t in targets_res.json()["data"]["activeTargets"]:
        if t["health"] == "up":
            targets.append((t["labels"]["job"],
                            t["labels"]["instance"],
                            t["scrapeUrl"]))
    while True:
        msgs = []
        for job, instance, url in targets:
            metrics = session.get(url)
            for mf in t2mf(metrics.content.decode('UTF-8')):
                for sample in mf.samples:
                    payload = {sample[0]: sample[2], 'tags': sample[1]}
                    fill = dict(job=job, metrics=mf.name, instance=instance)
                    msgs.append(
                        (topic.format(**fill), json.dumps(payload)))
        multiple(msgs, client_id=client_id, hostname=host, port=int(port))
        LOG.info(f"Wait for {wait}ms for next polling...")
        time.sleep(wait / 1000)
