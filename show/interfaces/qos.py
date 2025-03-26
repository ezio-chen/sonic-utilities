import click
import utilities_common.cli as clicommon
from natsort import natsorted

#
# qos group (show interfaces qos ...)
#
@click.command('qos')
@click.argument('interface_name', required=False)
@clicommon.pass_db
def qos(db, interface_name):
    """Show details of the QoS"""
    config_db = db.cfgdb
    ctx = click.get_current_context()
    qos_map_table_name = {
            'dot1p_to_tc_map': 'Dot1p to TC',
            'dscp_to_tc_map': 'DSCP to TC',
            'tc_to_pg_map': 'TC to PG',
            'tc_to_queue_map': 'TC to Queue',
            'pfc_to_queue_map': 'PFC to Queue',
            'pfc_to_pg_map': 'PFC to PG'
        }

    if interface_name is None:
        interface_list = []
        port_qos_map = config_db.get_table('PORT_QOS_MAP')
        keys = natsorted(port_qos_map.keys())

        for key in keys:
            qos_data = port_qos_map[key]
            interface_list.append(key)
            click.echo("{}:".format(key))
            if len(qos_data) != 0:
                for k in qos_data:
                    if k in qos_map_table_name:
                        data = qos_data[k]
                        click.echo("  {}: {}".format(qos_map_table_name[k], data))
                    if 'pfc_enable' == k:
                        click.echo("  {}: {}".format('pfc-priority', qos_data['pfc_enable']))
            click.echo("")
    else:
        qos_data = config_db.get_entry('PORT_QOS_MAP', interface_name)
        if len(qos_data) != 0:
            for k in qos_data:
                if k in qos_map_table_name:
                    data = qos_data[k]
                    click.echo("  {}: {}".format(qos_map_table_name[k], data))
                if 'pfc_enable' == k:
                    click.echo("  {}: {}".format('pfc-priority', qos_data['pfc_enable']))

def add_command(interfaces):
    interfaces.add_command(qos)