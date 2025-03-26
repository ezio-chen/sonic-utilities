import click
import utilities_common.cli as clicommon
import utilities_common.config_util as config_util
from sonic_py_common import device_info
from .main import update_qos_map_interface

#
# 'qos dot1p-tc' group ('config qos dot1p-tc ...')
#
@click.group('dot1p-tc')
def dot1p_tc():
    """Configure dot1p to TC mapping"""
    pass

def validate_qos_map_values(ctx, name, user_arg1, user_arg2, qos_map, max_value=8):
    values = user_arg1.split(',')
    for val in values:
        if '-' in val:
            start = val.split('-')[0]
            end = val.split('-')[1]
            if not start.isdigit() or not end.isdigit() or not 0 <= int(start) < max_value or not 0 <= int(end) < max_value or int(start) > int(end):
                ctx.fail("Invalid {} value {}, value should be in range of 0-{}.".format(name, user_arg1, max_value-1))
                return
            for i in range(int(start), int(end)+1):
                if str(i) in qos_map:
                    ctx.fail("{} value {} is repeated".format(name, i))
                else:
                    qos_map[str(i)] = user_arg2
        else:
            if not val.isdigit() or not 0 <= int(val) < max_value:
                ctx.fail("Invalid {} value {}, value should be in range of 0-{}.".format(name, user_arg1, max_value-1))
            if val in qos_map:
                ctx.fail("{} value {} is repeated.".format(name, val))
            else:
                qos_map[val] = user_arg2

def validate_qos_map_bind_interface(db, profile, qos_map_field):
    config_db = db.cfgdb
    ctx = click.get_current_context()

    port_qos_table = config_db.get_table('PORT_QOS_MAP')
    for k, v in port_qos_table.items():
        if qos_map_field in v:
            qos_map = v.get(qos_map_field, '')
            found = True if qos_map == profile else False
            if found:
                ctx.fail('The profile is binding to interface, unbind from it first.')

@dot1p_tc.command('add')
@click.argument('profile', metavar='<profile>', required=True)
@click.option('--dot1p', type=click.STRING, required=True, help="Cos value")
@click.option('--tc', type=click.IntRange(0, 7), required=True, help="Traffic-class(TC) value")
@clicommon.pass_db
def add(db, profile, dot1p, tc):
    """Add dot1p-tc map profile."""
    config_db = db.cfgdb
    ctx = click.get_current_context()
    entry = config_db.get_entry('DOT1P_TO_TC_MAP', profile)
    if len(entry) != 0:
        ctx.fail("Profile '{}' already exists use update command.".format(profile))

    dot1p_tc_map = {}
    validate_qos_map_values(ctx, "dot1p", dot1p, tc, dot1p_tc_map)

    config_db.mod_entry('DOT1P_TO_TC_MAP', profile, dot1p_tc_map)

@dot1p_tc.command('update')
@click.argument('profile', metavar='<profile>', required=True)
@click.option('--dot1p', type=click.STRING, required=True, help="Cos value")
@click.option('--tc', type=click.IntRange(0, 7), required=False, help="Traffic-class(TC) value")
@click.option('--remove', default=False, is_flag=True, help="Delete the mapping entry")
@clicommon.pass_db
def update(db, profile, dot1p, tc, remove):
    """Update dot1p-tc map profile."""
    config_db = db.cfgdb
    ctx = click.get_current_context()
    entry = config_db.get_entry('DOT1P_TO_TC_MAP', profile)
    if len(entry) == 0:
        ctx.fail("Profile '{}' not found.".format(profile))

    if remove == False and tc == None:
        ctx.fail('--tc is a required parameter.')

    dot1p_tc_map = {}
    validate_qos_map_values(ctx, "dot1p", dot1p, tc, dot1p_tc_map)
    validate_qos_map_bind_interface(db, profile, 'dot1p_to_tc_map')

    if remove:
        for i in dot1p_tc_map:
            if i in entry:
                del entry[i]

        if len(entry) != 0:
            config_db.set_entry('DOT1P_TO_TC_MAP', profile, entry)
        else:
            config_db.set_entry('DOT1P_TO_TC_MAP', profile, None)
    else:
        for i in entry:
            if i not in dot1p_tc_map:
                dot1p_tc_map[i] = entry[i]

        config_db.mod_entry('DOT1P_TO_TC_MAP', profile, dot1p_tc_map)

@dot1p_tc.command('del')
@click.argument('profile', metavar='<profile>', required=True)
@clicommon.pass_db
def delete(db, profile):
    """Delete dot1p-tc map profile."""
    config_db = db.cfgdb
    ctx = click.get_current_context()

    entry = config_db.get_entry('DOT1P_TO_TC_MAP', profile)
    if len(entry) == 0:
        ctx.fail("dot1p-tc profile '{}' not found.".format(profile))

    validate_qos_map_bind_interface(db, profile, 'dot1p_to_tc_map')

    config_db.set_entry('DOT1P_TO_TC_MAP', profile, None)

#
# 'qos dscp-tc' group ('config qos dscp-tc ...')
#
@click.group('dscp-tc')
def dscp_tc():
    """Configure dscp to TC mapping"""
    pass

@dscp_tc.command('add')
@click.argument('profile', metavar='<profile>', required=True)
@click.option('--dscp', type=click.STRING, required=True, help="Cos value")
@click.option('--tc', type=click.IntRange(0, 7), required=True, help="Traffic-class(TC) value")
@clicommon.pass_db
def add(db, profile, dscp, tc):
    """Add dscp-tc map profile."""
    config_db = db.cfgdb
    ctx = click.get_current_context()
    entry = config_db.get_entry('DSCP_TO_TC_MAP', profile)
    if len(entry) != 0:
        ctx.fail("Profile '{}' already exists use update command.".format(profile))

    dscp_tc_map = {}
    validate_qos_map_values(ctx, "dscp", dscp, tc, dscp_tc_map, 64)

    config_db.mod_entry('DSCP_TO_TC_MAP', profile, dscp_tc_map)

@dscp_tc.command('update')
@click.argument('profile', metavar='<profile>', required=True)
@click.option('--dscp', type=click.STRING, required=True, help="Cos value")
@click.option('--tc', type=click.IntRange(0, 7), required=False, help="Traffic-class(TC) value")
@click.option('--remove', default=False, is_flag=True, help="Delete the mapping entry")
@clicommon.pass_db
def update(db, profile, dscp, tc, remove):
    """Update dscp-tc map profile."""
    config_db = db.cfgdb
    ctx = click.get_current_context()
    entry = config_db.get_entry('DSCP_TO_TC_MAP', profile)
    if len(entry) == 0:
        ctx.fail("Profile '{}' not found.".format(profile))

    if remove == False and tc == None:
        ctx.fail('--tc is a required parameter.')

    dscp_tc_map = {}
    validate_qos_map_values(ctx, "dscp", dscp, tc, dscp_tc_map, 64)
    validate_qos_map_bind_interface(db, profile, 'dscp_to_tc_map')

    if remove:
        for i in dscp_tc_map:
            if i in entry:
                del entry[i]

        if len(entry) != 0:
            config_db.set_entry('DSCP_TO_TC_MAP', profile, entry)
        else:
            config_db.set_entry('DSCP_TO_TC_MAP', profile, None)
    else:
        for i in entry:
            if i not in dscp_tc_map:
                dscp_tc_map[i] = entry[i]

        config_db.mod_entry('DSCP_TO_TC_MAP', profile, dscp_tc_map)

@dscp_tc.command('del')
@click.argument('profile', metavar='<profile>', required=True)
@clicommon.pass_db
def delete(db, profile):
    """Delete dscp-tc map profile."""
    config_db = db.cfgdb
    ctx = click.get_current_context()

    entry = config_db.get_entry('DSCP_TO_TC_MAP', profile)
    if len(entry) == 0:
        ctx.fail("dscp-tc profile '{}' not found.".format(profile))

    validate_qos_map_bind_interface(db, profile, 'dscp_to_tc_map')

    config_db.set_entry('DSCP_TO_TC_MAP', profile, None)
#
# 'qos tc-pg' group ('config qos tc-pg ...')
#
@click.group('tc-pg')
def tc_pg():
    """Configure TC to priority-group mapping"""
    pass

@tc_pg.command('add')
@click.argument('profile', metavar='<profile>', required=True)
@click.option('--tc', type=click.STRING, required=True, help="Traffic-class(TC) value")
@click.option('--pg', type=click.IntRange(0, 7), required=True, help="Priority-group(PG) value")
@clicommon.pass_db
def add(db, profile, tc, pg):
    """Add tc-pg map profile."""
    config_db = db.cfgdb
    ctx = click.get_current_context()
    entry = config_db.get_entry('TC_TO_PRIORITY_GROUP_MAP', profile)
    if len(entry) != 0:
        ctx.fail("Profile '{}' already exists use update command.".format(profile))

    tc_pg_map = {}
    validate_qos_map_values(ctx, "tc", tc, pg, tc_pg_map)

    config_db.mod_entry('TC_TO_PRIORITY_GROUP_MAP', profile, tc_pg_map)

@tc_pg.command('update')
@click.argument('profile', metavar='<profile>', required=True)
@click.option('--tc', type=click.STRING, required=True, help="Traffic-class(TC) value")
@click.option('--pg', type=click.IntRange(0, 7), required=False, help="Priority-group(PG) value")
@click.option('--remove', default=False, is_flag=True, help="Delete the mapping entry")
@clicommon.pass_db
def update(db, profile, tc, pg, remove):
    """Update tc-pg map profile."""
    config_db = db.cfgdb
    ctx = click.get_current_context()
    entry = config_db.get_entry('TC_TO_PRIORITY_GROUP_MAP', profile)
    if len(entry) == 0:
        ctx.fail("Profile '{}' not found.".format(profile))

    if remove == False and pg == None:
        ctx.fail('--pg is a required parameter.')

    tc_pg_map = {}
    validate_qos_map_values(ctx, "tc", tc, pg, tc_pg_map)
    validate_qos_map_bind_interface(db, profile, 'tc_to_pg_map')

    if remove:
        for i in tc_pg_map:
            if i in entry:
                del entry[i]

        if len(entry) != 0:
            config_db.set_entry('TC_TO_PRIORITY_GROUP_MAP', profile, entry)
        else:
            config_db.set_entry('TC_TO_PRIORITY_GROUP_MAP', profile, None)
    else:
        for i in entry:
            if i not in tc_pg_map:
                tc_pg_map[i] = entry[i]

        config_db.set_entry('TC_TO_PRIORITY_GROUP_MAP', profile, None)
        config_db.mod_entry('TC_TO_PRIORITY_GROUP_MAP', profile, tc_pg_map)

@tc_pg.command('del')
@click.argument('profile', metavar='<profile>', required=True)
@clicommon.pass_db
def delete(db, profile):
    """Delete tc-pg map profile."""
    config_db = db.cfgdb
    ctx = click.get_current_context()
    entry = config_db.get_entry('TC_TO_PRIORITY_GROUP_MAP', profile)
    if len(entry) == 0:
        ctx.fail("tc-pg profile '{}' not found.".format(profile))

    validate_qos_map_bind_interface(db, profile, 'tc_to_pg_map')

    config_db.set_entry('TC_TO_PRIORITY_GROUP_MAP', profile, None)

#
# 'qos tc-queue' group ('config qos tc-queue ...')
#
@click.group('tc-queue')
def tc_queue():
    """Configure TC to queue mapping"""
    pass

@tc_queue.command('add')
@click.argument('profile', metavar='<profile>', required=True)
@click.option('--tc', type=click.STRING, required=True, help="Traffic-class(TC) value")
@click.option('--queue', type=click.IntRange(0, 7), required=True, help="Queue value")
@clicommon.pass_db
def add(db, profile, tc, queue):
    """Add tc-queue map profile."""
    config_db = db.cfgdb
    ctx = click.get_current_context()
    entries = config_db.get_table('TC_TO_QUEUE_MAP')

    asic_type = device_info.get_sonic_version_info().get('asic_type', '')
    if asic_type == 'barefoot' and len(entries) > 0:
        ctx.fail('Only one profile is supported on Intel platform.')

    if profile in entries:
        ctx.fail("Profile '{}' already exists use update command.".format(profile))

    tc_queue_map = {}
    validate_qos_map_values(ctx, "tc", tc, queue, tc_queue_map)

    config_util.create(ctx, "TC_TO_QUEUE_MAP", profile, tc_queue_map,
                       "QOS_TC_TO_QUEUE_MAP_TABLE")

@tc_queue.command('update')
@click.argument('profile', metavar='<profile>', required=True)
@click.option('--tc', type=click.STRING, required=True, help="Traffic-class(TC) value")
@click.option('--queue', type=click.IntRange(0, 7), required=False, help="Queue value")
@click.option('--remove', default=False, is_flag=True, help="Delete the mapping entry")
@clicommon.pass_db
def update(db, profile, tc, queue, remove):
    """Update tc-queue map profile."""
    config_db = db.cfgdb
    ctx = click.get_current_context()
    entry = config_db.get_entry('TC_TO_QUEUE_MAP', profile)
    if len(entry) == 0:
        ctx.fail("Profile '{}' not found.".format(profile))

    if remove == False and queue == None:
        ctx.fail('--queue is a required parameter.')

    tc_queue_map = {}
    validate_qos_map_values(ctx, "tc", tc, queue, tc_queue_map)
    validate_qos_map_bind_interface(db, profile, 'tc_to_queue_map')

    if remove:
        for i in tc_queue_map:
            if i in entry:
                del entry[i]

        config_util.delete(ctx, "TC_TO_QUEUE_MAP", profile)

        if len(entry) != 0:
            config_util.create(ctx, "TC_TO_QUEUE_MAP", profile, entry,
                               "QOS_TC_TO_QUEUE_MAP_TABLE")
    else:
        for i in entry:
            if i not in tc_queue_map:
                tc_queue_map[i] = entry[i]

        config_util.delete(ctx, "TC_TO_QUEUE_MAP", profile)
        config_util.create(ctx, "TC_TO_QUEUE_MAP", profile, tc_queue_map,
                           "QOS_TC_TO_QUEUE_MAP_TABLE")

@tc_queue.command('del')
@click.argument('profile', metavar='<profile>', required=True)
@clicommon.pass_db
def delete(db, profile):
    """Delete tc-queue map profile."""
    config_db = db.cfgdb
    ctx = click.get_current_context()
    entry = config_db.get_entry('TC_TO_QUEUE_MAP', profile)
    if len(entry) == 0:
        ctx.fail("tc-queue profile '{}' not found.".format(profile))

    validate_qos_map_bind_interface(db, profile, 'tc_to_queue_map')

    config_util.delete(ctx, "TC_TO_QUEUE_MAP", profile)

#
# 'qos' subgroup ('config interface qos ...')
#

@click.group('qos', cls=clicommon.AbbreviationGroup)
@click.pass_context
def qos_interface(ctx):
    """Set interface QoS configuration"""
    pass

@qos_interface.command('dot1p-tc')
@click.argument('op', metavar='{bind|unbind}', type=click.Choice(['bind', 'unbind']), required=True)
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('profile', metavar='<profile>', required=False)
@clicommon.pass_db
def dot1p_tc_interface(db, op, interface_name, profile):
    """dot1p-tc policy configuration"""
    if op == 'bind' and profile == None:
        ctx = click.get_current_context()
        ctx.fail("Cannot find dot1p-tc profile.")

    update_qos_map_interface(db, op, 'dot1p_to_tc_map', 'DOT1P_TO_TC_MAP', profile, interface_name)

@qos_interface.command('tc-pg')
@click.argument('op', metavar='{bind|unbind}', type=click.Choice(['bind', 'unbind']), required=True)
@click.argument('interface_name', metavar='{<interface_name>|all}', required=True)
@click.argument('profile', metavar='<profile>', required=False)
@clicommon.pass_db
def tc_pg_interface(db, op, interface_name, profile):
    """tc-pg policy configuration"""
    if op == 'bind' and profile == None:
        ctx = click.get_current_context()
        ctx.fail("Cannot find tc-pg profile.")

    interfaces = set()
    if interface_name.lower() == "all":
        config_db = db.cfgdb
        port_table = config_db.get_table('PORT')
        interfaces = set(port_table.keys())
    else:
        interfaces.add(interface_name)

    for intf in interfaces:
        update_qos_map_interface(db, op, 'tc_to_pg_map', 'TC_TO_PRIORITY_GROUP_MAP', profile, intf)

@qos_interface.command('tc-queue')
@click.argument('op', metavar='{bind|unbind}', type=click.Choice(['bind', 'unbind']), required=True)
@click.argument('interface_name', metavar='{<interface_name>|all}', required=True)
@click.argument('profile', metavar='<profile>', required=False)
@clicommon.pass_db
def tc_queue_interface(db, op, interface_name, profile):
    """tc-queue policy configuration"""
    ctx = click.get_current_context()

    if op == 'bind' and profile == None:
        ctx.fail("Cannot find tc-queue profile.")

    asic_type = device_info.get_sonic_version_info().get('asic_type', '')
    if asic_type == 'barefoot':
        ctx.fail('Not support to bind tc-queue profile on Intel platform.')

    interfaces = set()
    if interface_name.lower() == "all":
        config_db = db.cfgdb
        port_table = config_db.get_table('PORT')
        interfaces = set(port_table.keys())
    else:
        interfaces.add(interface_name)

    for intf in interfaces:
        update_qos_map_interface(db, op, 'tc_to_queue_map', 'TC_TO_QUEUE_MAP', profile, intf)

@qos_interface.command('dscp-tc')
@click.argument('op', metavar='{bind|unbind}', type=click.Choice(['bind', 'unbind']), required=True)
@click.argument('interface_name', metavar='<interface_name>', required=True)
@click.argument('profile', metavar='<profile>', required=False)
@clicommon.pass_db
def dscp_tc_interface(db, op, interface_name, profile):
    """dscp-tc policy configuration"""
    if op == 'bind' and profile == None:
        ctx = click.get_current_context()
        ctx.fail("Cannot find dscp-tc profile.")

    update_qos_map_interface(db, op, 'dscp_to_tc_map', 'DSCP_TO_TC_MAP', profile, interface_name)

def add_command(config_qos, interface):
    config_qos.add_command(dot1p_tc)
    config_qos.add_command(dscp_tc)
    config_qos.add_command(tc_pg)
    config_qos.add_command(tc_queue)

    interface.add_command(qos_interface)
