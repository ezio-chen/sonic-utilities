import click
import utilities_common.cli as clicommon
from natsort import natsorted
from sonic_py_common import device_info
from tabulate import tabulate

def show_qos_map(db, profile, table_name, header, qos_map_type, max_len=8):
    config_db = db.cfgdb
    ctx = click.get_current_context()
    body = []
    if profile is None:
        data = config_db.get_table(table_name)
        keys = natsorted(data.keys())
        for k in keys:
            body = []
            click.echo("{} policy: {}".format(qos_map_type, k))
            size = len(data[k])
            x = 0
            if size != 0:
                while x < max_len:
                    if str(x) in data[k]:
                        body.append([x, data[k].get(str(x))])
                    x+=1
                if len(body) != 0:
                    click.echo(tabulate(body, header, stralign='left'))
                    click.echo("")
    else:
        data = config_db.get_entry(table_name, profile)
        size = len(data)
        x = 0
        if size != 0:
            click.echo("{} policy: {}".format(qos_map_type, profile))
            while x < max_len:
                if str(x) in data:
                    body.append([x, data.get(str(x))])
                x+=1
            if len(body) != 0:
                click.echo(tabulate(body, header, stralign='left'))

#
# 'qos dot1p-tc' command ("show qos dot1p-tc ")
#
@click.command('dot1p-tc')
@click.argument('profile', required=False)
@clicommon.pass_db
def dot1p_tc(db, profile):
    '''Show dot1p to TC qos policy'''
    header = ['Dot1p', 'TC']
    show_qos_map(db, profile, 'DOT1P_TO_TC_MAP', header, 'dot1p-tc')

#
# 'qos dscp-tc' command ("show qos dscp-tc ")
#
@click.command('dscp-tc')
@click.argument('profile', required=False)
@clicommon.pass_db
def dscp_tc(db, profile):
    '''Show DSCP to TC qos policy'''
    config_db = db.cfgdb
    ctx = click.get_current_context()

    profile_data = {}
    data = config_db.get_table('DSCP_TO_TC_MAP')

    for key in data.keys():
        if profile is None or profile == key:
            profile_data[key] = {}

            for dscp,tc in data.get(key).items():
                if tc not in profile_data[key]:
                    profile_data[key][tc] = []

                profile_data[key][tc].append(dscp)

    header = ['DSCP', 'TC']
    for name in natsorted(list(profile_data.keys())):
        p_data = profile_data.get(name)
        body = []

        for tc in natsorted(list(p_data.keys())):
            e = p_data.get(tc)
            body.append([' '.join(e), tc])

        click.echo("dscp-tc policy: {}".format(name))
        click.echo(tabulate(body, header, stralign='left') + '\n')

#
# 'qos tc-pg' command ("show qos tc-pg ")
#
@click.command('tc-pg')
@click.argument('profile', required=False)
@clicommon.pass_db
def tc_pg(db, profile):
    '''Show TC to priority-group qos policy'''
    header = ['TC', 'PG']
    show_qos_map(db, profile, 'TC_TO_PRIORITY_GROUP_MAP', header, 'tc-pg')

#
# 'qos tc-queue' command ("show qos tc-queue ")
#
@click.command('tc-queue')
@click.argument('profile', required=False)
@clicommon.pass_db
def tc_queue(db, profile):
    '''Show TC to queue qos policy'''
    header = ['TC', 'Queue']
    show_qos_map(db, profile, 'TC_TO_QUEUE_MAP', header, 'tc-queue')

def add_command(show_qos):
    show_qos.add_command(dot1p_tc)
    show_qos.add_command(dscp_tc)
    show_qos.add_command(tc_pg)
    show_qos.add_command(tc_queue)
