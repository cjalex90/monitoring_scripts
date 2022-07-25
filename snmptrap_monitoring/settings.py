LOG_DIRECTORY = "/var/log/snmptrap_monitoring"
LOG_SNMPTRAP = "snmptrap.log"
LOG_SNMPTRAP_EXCEPTION = "snmptrap_exception.log"
LOG_EVENT = "event.log"
LOG_PARSED_EVENT = "parsed_event.log"
LOG_PARSED_EVENT_EXCEPTION = "parsed_event_exception.log"
LOG_ERROR = "error.log"
LOG_TIMEFORMAT = "%Y.%m.%d %H:%M:%S"
LOG_MAXSIZE = 10485760


ELASTIC_CLUSTERS = [
    [
        "http://es1-monitoring1.domain.local:9200",
        "http://es1-monitoring2.domain.local:9200",
        "http://es1-monitoring3.domain.local:9200"
    ],
    [
        "http://es2-monitoring1.domain.local:9200",
        "http://es2-monitoring2.domain.local:9200"
    ]
]

ZABBIX_SERVER = "zabbix.domain.local"


SENDING_RULES = {
    "Storage": {
        "zabbix": {
            "snmptrap-storage": "storage_events"
        },
        "elastic": "snmptrap_storage"
    },
    "vROps": {
        "zabbix": {
            "snmptrap_vrops": "vrops_events"
        },
        "elastic": "snmptrap_vrops"
    },
    "other": {
        "zabbix": {
            "snmptrap-test": "unknown_events"
        }
    }
}


SNMPTRAP_MISSED_FIELDS = [
    "<UNKNOWN>",
    "SNMP-COMMUNITY-MIB::snmpTrap",
    "SNMPv2-MIB::snmpTrap",
    "DISMAN-EVENT-MIB"
]

SNMPTRAP_OID_FIELDS = [
    "iso.",
    "SNMPv2-SMI::enterprises.",
    "SNMPv2-SMI::experimental."
]


IBM_FS5100 = {
    "System Name": "2.6.190.4.7",
    "Error ID": "2.6.190.4.3",
    "Error Code": "2.6.190.4.3",
    "Object Type": "2.6.190.4.11",
    "Object ID": "2.6.190.4.12",
    "Object name": "2.6.190.4.17",
    "rules": {
        "substitution": {
            ".": {
                "# .+ = ": ""
            }
        }
    }
}

IBM_FS900 = {
    "System Name": "2.6.255.1.1.7.7",
    "Error ID": "2.6.255.1.1.7.3",
    "Error Code": "2.6.255.1.1.7.4",
    "Object Type": "2.6.255.1.1.7.11",
    "Object ID": "2.6.255.1.1.7.12",
    "Object name":"2.6.255.1.1.7.17",
    "rules": {
        "substitution": {
            ".": {
                "# .+ = ": ""
            }
        }
    }
}

VROPS = {
    "Source": "6876.4.50.1.2.2.0",
    "Source": "6876.4.50.1.2.2",
    "Severity": "6876.4.50.1.2.5.0",
    "Severity": "6876.4.50.1.2.5",
    "Error": "6876.4.50.1.2.17.0",
    "Error": "6876.4.50.1.2.17",
    "Notification": "6876.4.50.1.2.20.0",
    "Notification": "6876.4.50.1.2.20"
}


SOURCES = {
    "Storage": [
        IBM_FS5100,
        IBM_FS900
    ],
    "vrops": [
        VROPS
    ]
}


EXCEPTIONS = [
    "Space Efficient Virtual Disk Copy space warning",
    "A volume size was changed",
    "A mapping or masking operation for a volume was performed",
    "A scrub-disk-group job completed",
    "Details associated with a scrub-disk-group job",
    "IF-MIB::linkDown",
    "IF-MIB::linkUp",
    "SNMPv2-MIB::coldStart",
    "SNMPv2-MIB::warmStart",
    "NET-SNMP-AGENT-MIB::nsNotifyRestart"
]