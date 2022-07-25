import os
import sys
import json
import traceback
import subprocess
import logging
import logging.handlers

import paramiko

TAG_HOST = "storage"

LOG_DIRECTORY = "/var/log/telegraf/scripts/"
LOG_FILENAME = f"{os.path.basename(__file__)}_error.log"
LOG_TIMEFORMAT = "%Y.%m.%d %H:%M:%S"
LOG_MAXSIZE = 1048576

SCRIPT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
HOSTS_FILENAME = f"{SCRIPT_DIRECTORY}/storages.csv"

USER = "user"
PASSWORD = "password"

METRICS = {
    "capacity": {
        "compression": [
            "physical_capacity",
            "total_vdisk_capacity",
            "physical_free_capacity"
        ],
        "nocompression": {
            "pool": [
                "capacity",
                "free_capacity"
            ],
            "total": [
                "total_mdisk_capacity",
                "total_free_space"
            ] 
        }
    },
    "statistic": [
        "cpu_pc",
        "mdisk_w_ms",
        "mdisk_r_ms",
        "mdisk_w_mb",
        "mdisk_r_mb",
        "mdisk_w_io",
        "mdisk_r_io",
        "write_cache_pc"
    ],
    "iogroup": [
        "vdisk_mb",
        "vdisk_io"
    ]
}


def log(message: str) -> None:
    log_handler = logging.handlers.RotatingFileHandler(
        f"{LOG_DIRECTORY}/{LOG_FILENAME}",
        maxBytes=LOG_MAXSIZE,
        backupCount=5)
    formatter = logging.Formatter(
        "%(asctime)s %(message)s", LOG_TIMEFORMAT)
    log_handler.setFormatter(formatter)
    logger = logging.getLogger()
    logger.addHandler(log_handler)
    logger.error(message)


class Storwize:
    def __init__(self, host, user, password):
        self.host = host
        self.user = user
        self.password = password

        self.host_tag = "storage"
        self.ssh_client = None

    def __del__(self):
        if self.ssh_client:
            self.ssh_client.close()

    def _get_data(
            self, metrics_data, metrics, entity_pos=None, tag=None, entity=None):
        result = []
        series = {}
        if metrics:
            for metric_name in metrics:
                for data in metrics_data:
                    if metric_name in data.split(":"):
                        series[self.host_tag] = self.host
                        if entity_pos:
                            metric_value = data.split(":")[entity_pos]
                            series[tag] = entity
                        else:
                            metric_value = data.split(":")[1]
                        series[metric_name] = int(metric_value)
        else:
            result.extend(metrics_data)

        if series:
            result.append(series)
        return result

    def _get_metrics(
            self, metrics, first_command, entity_pos=None, tag=None):
        delimiter = "-delim :"
        result = []
        full_command = f"{first_command} {delimiter}"
        _, stdout, _ = self.ssh_client.exec_command(full_command)
        metrics_data = self._get_ssh_output(stdout)
        if entity_pos:
            entities = []

            for data in metrics_data:
                entity_name = data.split(":")[1]
                if entity_name not in entities:
                    entities.append(entity_name)
            for entity in entities:
                metrics_data = []
                _, stdout, _ = self.ssh_client.exec_command(
                    f"{first_command} {delimiter} {entity}")
                metrics_data.extend(self._get_ssh_output(stdout))
                result.extend(self._get_data(
                    metrics_data, metrics, entity_pos, tag, entity))
        else:
            result.extend(self._get_data(metrics_data, metrics))
        return result

    def get_avail_metric(self) -> dict:
        response = subprocess.call(
            f"ping -c 1 {self.host}".split(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
        result = {
            self.host_tag: self.host,
            "avail": response
        }
        return result

    def _get_ssh_output(self, stdout):
        output = stdout.read().decode().split("\n")[:-1]
        return output

    def get_capacity_metrics(self, metrics: list) -> list:
        command = "lssystem -bytes"
        result = self._get_metrics(metrics, command)
        return result

    def get_iogroups_metrics(self, metrics: list, command: str) -> list:
        result = self._get_metrics(metrics, command, 3, "iogroup")
        return result

    def get_pools_metrics(self, metrics: list) -> list:
        command = "lsmdiskgrp -bytes"
        result = self._get_metrics(metrics, command, 1, "pool")
        return result

    def count_alerts(self):
        command = "lseventlog -message no -nohdr"
        result = 0
        alerts = self._get_metrics(None, command)
        for alert in alerts:
            error_code = alert.split(":")[-2]
            if error_code:
                result += 1
        return result

    def get_system_metrics(self, metrics: list) -> list:
        command = "lssystemstats"
        result = self._get_metrics(metrics, command)
        return result

    def set_host_tag(self, tag: str) -> None:
        self.host_tag = tag

    def ssh_connect(self) -> None:
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh_client.connect(
            self.host,
            username=self.user,
            password=self.password,
            look_for_keys=False)


def main() -> None:
    result = []
    try:
        with open(HOSTS_FILENAME) as file:
            hosts_data = file.read().splitlines()
            for data in hosts_data:
                host, compression = data.split(",")
                storage = Storwize(host, USER, PASSWORD)
                storage.ssh_connect()
                storage.set_host_tag(TAG_HOST)
                count_alerts = storage.count_alerts()
                alerts_metrics = {
                    TAG_HOST: host,
                    "count_alerts": count_alerts,
                    "health_status": 0
                }
                if count_alerts:
                    alerts_metrics["health_status"] = 2
                result.append(alerts_metrics)
                if compression == "compression":
                    pool_capacity_metrics = METRICS["capacity"]["compression"]
                    total_capacity = pool_capacity_metrics
                    iogroups_command = "lsnodestats"
                else:
                    pool_capacity_metrics = METRICS["capacity"]["nocompression"]["pool"]
                    total_capacity = METRICS["capacity"]["nocompression"]["total"]
                    iogroups_command = "lsnodecanisterstats"
                result.extend(storage.get_capacity_metrics(
                    total_capacity))
                result.extend(storage.get_pools_metrics(
                    pool_capacity_metrics))
                result.extend(storage.get_system_metrics(
                    METRICS["statistic"]))
                result.extend(storage.get_iogroups_metrics(
                    METRICS["iogroup"], iogroups_command))
                result.append(storage.get_avail_metric())

    except:
        log_message = f"{host}:\n{traceback.format_exc()}"
        print(log_message, file=sys.stderr)
        log(log_message)
        pass

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
