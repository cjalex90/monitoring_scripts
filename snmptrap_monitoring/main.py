import re
import sys
import socket
import logging
import logging.handlers
from datetime import datetime

from pyzabbix import ZabbixMetric, ZabbixSender
from elasticsearch import Elasticsearch

from settings import *


def event_parser(event):
    current_system = None
    result = {}

    def _find(value, pattern = " value: (.+)"):
        if re.findall(f"{value}{pattern}", event):
            return re.findall(f"{value}{pattern}", event)[0]
    
    def _resolve(ip):
        try:
            for dname in socket.gethostbyaddr(ip):
                if isinstance(dname, str):
                    return dname
        except socket.error:
            return ip

    for source_name, source in SOURCES.items():
        for system in source:
            for comment, oid in system.items():
                if _find(oid):
                    current_system = system
                    if not source_name in current_system:
                        result.update({source_name: _resolve(_find("UDP",
                        pattern=": \[(.+)]:.+>"))})
                    result.update({comment: _find(oid)})

    if result and "rules" in current_system:
        if "substitution" in current_system["rules"]:
            for rule_comment, rule in current_system["rules"]["substitution"].items():
                for sub_pattern, sub_value in rule.items():
                    for comment in result.keys():
                        if re.search(rule_comment, comment):
                            result[comment] = re.sub(
                                sub_pattern,
                                sub_value,
                                result[comment])
        if "exceptions" in current_system["rules"]:
            for exception in current_system["rules"]["exceptions"]:
                coincidences = 0
                for comment in exception:
                    if exception[comment] in result[comment]:
                        coincidences += 1
                if coincidences == len(exception):
                    logger(LOG_PARSED_EVENT_EXCEPTION, f"{result}\n")
                    exit()
    return result


def zabbix_send(zabbix_host, key, message):
    metrics = []
    m = ZabbixMetric(zabbix_host, key, message)
    metrics.append(m)
    zbx = ZabbixSender(ZABBIX_SERVER)
    zbx.send(metrics)


def elastic_send(cluster, source, message):
    now = datetime.now()
    id_name = f"id{now.strftime('%Y%m%d%H%M%S%f')}"
    index_name = f"{source}-{now.utcnow().strftime('%Y.%m.%d')}"
    timestamp = now.astimezone().isoformat()
    message["@timestamp"] = timestamp
    message["vision"] = "sys"
    
    es = Elasticsearch(cluster)
    es.create(index=index_name, id=id_name, document=message, refresh=True)


def logger(logfile, message):
    log_handler = logging.handlers.RotatingFileHandler(
        f"{LOG_DIRECTORY}/{logfile}",
        maxBytes=LOG_MAXSIZE,
        backupCount=5)
    log_handler.terminator = ""
    formatter = logging.Formatter(
        "%(asctime)s.%(msecs)03d %(message)s", LOG_TIMEFORMAT)
    log_handler.setFormatter(formatter)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(log_handler)
    logger.info(f"{logfile.split('.')[0].upper()}\n{message}")
    logger.removeHandler(log_handler)


def main():
    try:
        snmptrap = sys.stdin.readlines()
        snmptrap_string = "".join(snmptrap)
        logger(LOG_SNMPTRAP, snmptrap_string)

        event = ""
        for line in snmptrap:
            if re.search("UDP", line):
                event += line
            for field in SNMPTRAP_MISSED_FIELDS:
                if re.search(field, line):
                    line = ""
            for field in SNMPTRAP_OID_FIELDS:
                if re.search(field, line):
                    line = line.replace(" ", " value: ", 1)
                    line = line.replace(field, "oid: ", 1)
                    line = line.replace('"', "")
                    event += line

        logger(LOG_EVENT, event)
        parsed_event = event_parser(event)

        for exception in EXCEPTIONS:
            if exception in snmptrap_string:
                logger(LOG_SNMPTRAP_EXCEPTION, snmptrap_string)
                exit()

        for source, monitoring in SENDING_RULES.items():
            if parsed_event:
                logger(LOG_PARSED_EVENT, f"{parsed_event}\n")

                zabbix_event = ""
                for comment, value in parsed_event.items():
                    zabbix_event += f"{comment}: {value}\n"

                if source in parsed_event:
                    if "elastic" in monitoring:
                        for cluster in ELASTIC_CLUSTERS:
                            elastic_send(cluster, monitoring["elastic"], parsed_event)
                    if "zabbix" in monitoring:
                        for zabbix_host, zabbix_key in monitoring["zabbix"].items():
                            zabbix_send(zabbix_host, zabbix_key, zabbix_event)
            else:
                if source == "other":
                    for zabbix_host, zabbix_key in monitoring["zabbix"].items():
                        zabbix_send(zabbix_host, zabbix_key, event)
        
    except Exception as e:
        print(e)
        logger(LOG_ERROR, f"{e}\n{snmptrap_string}\n")
        pass


if __name__ == "__main__":
    main()
