import os
import json
import requests
import logging
import logging.handlers
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

LOG_DIRECTORY = "/var/log/telegraf/scripts/"
LOG_FILENAME = f"{os.path.basename(__file__)}_error.log"
LOG_TIMEFORMAT = "%Y.%m.%d %H:%M:%S"
LOG_MAXSIZE = 1048576

USER = "user"
PASSWORD = "password"
DOMAIN = "domain.local"

VC_HOSTS = [
    {
        "vc1.domain.local": "vc1-vrops.domain.local",
        "vc2.domain.local": "vc2-vrops.domain.local",
        "vc2.domain.local": "vc3-vrops.domain.local",
    }
]


def logger(message):
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

class Vrops:
    def __init__(self, address, vc_name):
        self.address = address
        self.vc_name = vc_name
        self.header = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        self.status = 0
        self.tags = None

    def _request(self, suffix, query_method, query = None):
        response = requests.request(
            query_method, f"https://{self.address}/suite-api/" + suffix, verify=False,
            headers=self.header, data=json.dumps(query))
        response.close()
        self.status = response.status_code
        return response.json()

    def _get_resources(self, resourcekind):
        resource_query = {"resourceKind": [resourcekind]}
        resource_data = self._request(
            'api/resources/query', 'POST', resource_query)
        result = {}
        for res in resource_data['resourceList']:
            id = res['identifier']
            name = res['resourceKey']['name']
            result[id] = name
        return result

    def _get_relations(self, resource_ids, resourcekinds):
        relation_query = {
            "relationshipType": "ALL",
            "resourceIds": resource_ids,
            "resourceQuery": {
            "resourcekind": resourcekinds
            }
        }
        
        result = {}
        relationships = self._request(
            'api/resources/bulk/relationships',
            'POST', relation_query)
        for id in resource_ids:
            result[id] = {}

            for res in relationships['resourcesRelations']:
                if id in res['relatedResources']:
                    key = res['resource']['resourceKey']['resourceKindKey']
                    name = res['resource']['resourceKey']['name']
                    result[id].update({key: name})
        return result
    
    def _get_value(self, resource_ids, metric_name):
        if ":" in metric_name:
            metric_prefix = metric_name.split('|')[0]
            metric_entity = metric_prefix.split(':')[1]
            metric_name = "".join(metric_name.split(metric_entity))
        metric_query = {
            "resourceId": resource_ids,
            "statKey": [metric_name]
        }
        metrics = self._request(
            "/api/resources/stats/latest/query", "POST", metric_query)
        result = {}
        count = []
        for id in resource_ids:
            result[id] = {}
            for metric in metrics["values"]:
                if id == metric["resourceId"]:
                    stats = metric["stat-list"]["stat"]
                    for stat in stats:
                        stat_name = stat["statKey"]["key"]
                        if ":" in stat_name:
                            name = stat_name.split(":")[1].split("|")[0]
                            count.append(name)
                            value = int(stat["data"][0])
                            result[id].update({name: value})
        return result

    def auth(self, user, password, domain):
        auth_query = {
            "username": user,
            "authSource": domain,
            "password": password
        }
        token = self._request(
            "api/auth/token/acquire", "POST", auth_query)["token"]
        self.header.update({"Authorization": f"vRealizeOpsToken {token}"})

    def get_metrics(self, resource_tag, metric_name, **resourcekind):
        resources = self._get_resources(list(resourcekind.values())[0])
        resource_ids = []
        for id in resources:
            resource_ids.append(id)
        tag_kinds = []
        if self.tags:
            for tag_kind in self.tags:
                tag_kinds.append(self.tags[tag_kind])
        
        related_resources = self._get_relations(
            resource_ids, tag_kinds)
        metrics_data = self._get_value(resource_ids, metric_name)

        result = []
        for id, metrics in metrics_data.items():
            for name, value in metrics.items():
                metric_output = metric_name.split("|")[1]
                series = {
                    "vcenter": self.vc_name,
                    list(resourcekind)[0]: resources[id],
                    resource_tag: name,
                    metric_output: value
                }
                if self.tags:
                    for tag_name, tag_value in self.tags.items():
                        relation = related_resources[id]
                        if tag_value in relation:
                            series[tag_name] = relation[tag_value]
                if series not in result:
                    result.append(series)
        return result

    def get_service_metric(self):
        result = {
            "url": self.address,
            "status": self.status
        }
        return result

    def set_tags(self, **tags):
        self.tags = tags


def main():
    result = []
    for vc in VC_HOSTS:
        try:
            for vc_name, address in vc.items():
                vrops = Vrops(address, vc_name)
                vrops.auth(USER, PASSWORD, DOMAIN)
                status = vrops.get_service_metric()
                result.append(status)
                vrops.set_tags(
                    dsname="Datastore",
                    cluster="ClusterComputeResource",
                )
                metrics = vrops.get_metrics(
                    "disk",
                    "disk:naa|diskqueued",
                    esxihost="HostSystem"
                )
                if metrics:
                    result.extend(metrics)
            print(json.dumps(result, indent=2))
        except Exception as e:
            logger(f"{vc_name}: {e}")


if __name__ == "__main__":
    main()
