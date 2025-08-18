import click
import string
import utilities_common.cli as clicommon
import utilities_common.config_util as config_util
import utilities_common.asic_info as asic_info
from sonic_py_common import device_info
from .utils import log
from .main import is_valid_profile_name
from .main import COS_RANGE, TC_RANGE, DSCP_RANGE

MAX_ACL_TABLE_TYPE_NAME_LEN = 16
MAX_ACL_RULE_NAME_LEN = 16

ACL_TABLE_TYPE_NAME_ALLOWED_CHAR = string.digits + string.ascii_lowercase + string.ascii_uppercase + '_' + '-'
ACL_RULE_NAME_ALLOWED_CHAR = string.digits + string.ascii_lowercase + string.ascii_uppercase + '_' + '-'

#
# 'acl' group ('config acl ...')
#
@click.group(cls=clicommon.AbbreviationGroup)
def acl():
    """ACL-related configuration tasks"""
    pass

#
# 'add' subgroup ('config acl add ...')
#
@acl.group(cls=clicommon.AbbreviationGroup)
def add():
    """
    Add ACL configuration.
    """
    pass


def get_acl_bound_ports(config_db):
    ports = set()
    portchannel_members = set()

    portchannel_member_dict = config_db.get_table("PORTCHANNEL_MEMBER")
    for key in portchannel_member_dict:
        ports.add(key[0])
        portchannel_members.add(key[1])

    port_dict = config_db.get_table("PORT")
    for key in port_dict:
        if key not in portchannel_members:
            ports.add(key)

    return list(ports)


def expand_vlan_ports(config_db, port_name):
    """
    Expands a given VLAN interface into its member ports.

    If the provided interface is a VLAN, then this method will return its member ports.

    If the provided interface is not a VLAN, then this method will return a list with only
    the provided interface in it.
    """
    if port_name not in config_db.get_keys("VLAN"):
        return [port_name]

    vlan_members = config_db.get_keys("VLAN_MEMBER")

    members = [member for vlan, member in vlan_members if port_name == vlan]

    if not members:
        raise ValueError("Cannot bind empty VLAN {}".format(port_name))

    return members


def parse_acl_table_info(ctx, table_name, table_type, description, ports, stage,
                         set_policer, config_db):
    if table_type not in ['L3', 'L3V6', 'MIRROR', 'MIRRORV6', 'MIRROR_DSCP', 'CTRLPLANE']:
        acl_table_types = config_db.get_table('ACL_TABLE_TYPE')

        if table_type not in acl_table_types:
            raise click.BadParameter('Table type {} is not exists'.format(table_type))

    table_info = {"type": table_type}

    if description:
        table_info["policy_desc"] = description
    else:
        table_info["policy_desc"] = table_name

    if not ports and ports != None:
        ctx.fail("Cannot bind empty list of ports")

    port_list = []
    valid_acl_ports = get_acl_bound_ports(config_db)

    if ports:
        for port in ports.split(","):
            port_list += expand_vlan_ports(config_db, port)
        port_list = list(set(port_list))  # convert to set first to remove duplicate ifaces
    else:
        port_list = valid_acl_ports

    for port in port_list:
        if port not in valid_acl_ports:
            ctx.fail("Cannot bind ACL to specified port {}".format(port))

    version_info = device_info.get_sonic_version_info()
    asic_type = version_info.get('asic_type')

    if table_type in ['MIRROR', 'MIRRORV6', 'MIRROR_DSCP'] and stage == 'egress':
        if asic_type == 'broadcom':
            ctx.fail("On Broadcom switches, {} is not supported on egress stage.".format(table_type))

    if asic_type == 'barefoot':
        if table_type == 'MIRROR_DSCP':
            p4_profile = device_info.get_localhost_info('p4_profile')

            if p4_profile != None and p4_profile != 'y2_profile':
                ctx.fail("MIRROR_DSCP is supported only on y2_profile.")

    table_info["ports@"] = ",".join(port_list)

    table_info["stage"] = stage

    actions = []
    if set_policer:
        actions.append('set_policer')

    if (actions):
        table_info["actions@"] = ",".join(actions)

    return table_info

#
# 'table' subcommand ('config acl add table ...')
#

def validate_services(ctx, param, value):
    if value == None:
        return None

    service_list = value.split(',')

    for s in service_list:
        if s not in ['SSH', 'SNMP', 'NTP']:
            raise click.BadParameter('{} is not a valid service.'.format(value))

    return service_list


#
# 'add' subcommand ('config acl add table ...')
#
@add.command()
@click.argument("table_name", metavar="<table_name>")
@click.argument('table_type', metavar="<table_type>")
@click.option("-d", "--description")
@click.option("-p", "--ports")
@click.option("-s", "--stage", type=click.Choice(["ingress", "egress"]), default="ingress")
@click.option("-S", "--services", callback=validate_services)
@click.option('--set-policer', is_flag=True, required=False)
@click.pass_context
def table(ctx, table_name, table_type, description, ports, stage, services, set_policer):
    """Add ACL table.

    Table type. Available types are L3, L3V6, MIRROR, MIRRORV6, MIRROR_DSCP, CTRLPLANE, and custom defined types.
    """
    config_db = ctx.obj.cfgdb

    if len(config_db.get_entry('ACL_TABLE', table_name)) != 0:
        raise click.BadParameter('{} already exists'.format(table_name))

    table_info = parse_acl_table_info(ctx, table_name, table_type, description, ports, stage,
                                      set_policer, config_db)

    if 'CTRLPLANE' == table_type.upper():
        if services:
            table_info["services@"] = ",".join(services)
        else:
            raise click.BadParameter('{} is required'.format(table_type))

        config_db.set_entry("ACL_TABLE", table_name, table_info)

    else:
        config_util.create(ctx, "ACL_TABLE", table_name, table_info,
                           state_db_table_name='ACL_TABLE_TABLE')


def validate_acl_table_type_name(ctx, param, table_type_name):
    if len(table_type_name) > MAX_ACL_TABLE_TYPE_NAME_LEN:
        raise click.BadParameter('Table type name exceeds the limit ({}).'.format(MAX_ACL_TABLE_TYPE_NAME_LEN))

    if not is_valid_profile_name(table_type_name, ACL_TABLE_TYPE_NAME_ALLOWED_CHAR):
        raise click.BadParameter('Table type name contains disallowed characters.')

    return table_type_name

def validate_bind_points(ctx, param, value):
    if value == None:
        return None

    bind_point_list = value.split(',')

    for s in bind_point_list:
        if s.upper() not in ['PORT', 'PORTCHANNEL']:
            raise click.BadParameter('{} is not a valid bind point.'.format(value))

    return bind_point_list


#
# 'add' subcommand ('config acl add table-type ...')
#
@click.command('table-type')
@click.pass_context
@click.argument('type_name', metavar='<type_name>', callback=validate_acl_table_type_name)
@click.option('--bind-points', callback=validate_bind_points, required=False,
    help='A comma-separated list of interface types that can be bound to the ACL table type. Valid values are "PORT" and "PORTCHANNEL". The default value is "PORT".')
@click.option('--match-src-ip4', is_flag=True, required=False,
    help='Specifies that the ACL table type can match the source IP address of IPv4 packets. This parameter cannot be specified with match-src-ip6 and match-dst-ip6 at the same time.')
@click.option('--match-dst-ip4', is_flag=True, required=False,
    help='Specifies that the ACL table type can match the destination IP address of IPv4 packets. This parameter cannot be specified with match-src-ip6 and match-dst-ip6 at the same time.')
@click.option('--match-src-ip6', is_flag=True, required=False,
    help='Specifies that the ACL table type can match the source IP address of IPv6 packets. This parameter cannot be specified with match-src-ip4 and match-dst-ip4 at the same time.')
@click.option('--match-dst-ip6', is_flag=True, required=False,
    help='Specifies that the ACL table type can match the destination IP address of IPv6 packets. This parameter cannot be specified with match-src-ip4 and match-dst-ip4 at the same time.')
@click.option('--match-dscp', is_flag=True, required=False,
    help='Specifies that the ACL table type can match the DSCP value of IP packets.')
@click.option('--match-l4-src-port', is_flag=True, required=False,
    help='Specifies that the ACL table type can match the source port of TCP/UDP packets.')
@click.option('--match-l4-dst-port', is_flag=True, required=False,
    help='Specifies that the ACL table type can match the destination port of TCP/UDP packets.')
@click.option('--match-vlan-id', is_flag=True, required=False,
    help='Specifies that the ACL table type can match the VLAN ID of IP packets.')
@click.option('--match-cos', is_flag=True, required=False,
    help='Specifies that the ACL table type can match the VLAN PCP of IP packets.')
def table_type_add(ctx, bind_points,
                   type_name, match_src_ip4, match_dst_ip4,
                   match_src_ip6, match_dst_ip6, match_dscp,
                   match_l4_src_port, match_l4_dst_port,
                   match_vlan_id, match_cos):
    """Add ACL table type."""
    asic = asic_info.get_asic_info()
    if asic.is_bf:
        ctx.fail('ACL table type is not supported on this device.')

    table_name = 'ACL_TABLE_TYPE'
    config_db = ctx.obj.cfgdb

    if asic.is_td4:
        # TD4 only support IP_TYPE = v4 or v6
        if not (match_src_ip4 or match_dst_ip4 or match_src_ip6 or match_dst_ip6):
            ctx.fail('Either (match-src-ip4 and match-dst-ip4) for IPv4 or (match-src-ip6 and match-dst-ip6) for IPv6 are required.')

    if len(config_db.get_entry(table_name, type_name)) != 0:
        raise click.BadParameter('{} already exists'.format(type_name))

    if (match_src_ip4 or match_dst_ip4) and (match_src_ip6 or match_dst_ip6):
        raise click.BadParameter('IPv4 and IPv6 addresses cannot specified at the same time.')

    matches = []

    if match_src_ip4:
        matches.append('src_ip')
    if match_dst_ip4:
        matches.append('dst_ip')
    if match_src_ip6:
        matches.append('src_ipv6')
    if match_dst_ip6:
        matches.append('dst_ipv6')
    if match_dscp:
        matches.append('dscp')
    if match_l4_src_port:
        matches.append('l4_src_port')
    if match_l4_dst_port:
        matches.append('l4_dst_port')
    if match_vlan_id:
        matches.append('vlan_id')
    if match_cos:
        matches.append('vlan_pri')

    if len(matches) == 0:
        raise click.BadParameter('Match is required.')

    matches.append('ip_type')

    actions = ['packet_action']

    if bind_points == None:
        bind_points = ['PORT']

    type_config = {
        'matches': matches,
        'actions': actions,
        'bind_points': bind_points
    }

    config_util.create(ctx, table_name, type_name, type_config,
                       state_db_table_name='ACL_TABLE_TYPE_TABLE')


def get_next_rule_priority(config_db, acl_table_name, max_priority):
    """Get next rule priority, the priority will be 10000, 9990, ..."""
    current_min_prio = max_priority + 1
    rules = config_db.get_table('ACL_RULE')

    for key, rule in rules.items():
        if key[0] != acl_table_name:
            continue

        priority = int(rule.get('PRIORITY', max_priority + 1))

        if priority < current_min_prio:
            current_min_prio = priority

    next_priority = (current_min_prio - 1) // 10 * 10

    if next_priority >= 1:
        return next_priority

    return None


def get_ip_type_by_acl_table_type(config_db, table_type):
    if table_type in ['L3', 'MIRROR']:
        return 'IPV4ANY'
    elif table_type in ['L3V6', 'MIRRORV6']:
        return 'IPV6ANY'
    elif table_type == 'MIRROR_DSCP':
        return None
    elif table_type == 'CTRLPLANE':
        return None
    else:
        user_table_type = config_db.get_entry('ACL_TABLE_TYPE', table_type)
        if user_table_type:
            matches = user_table_type.get('matches', [])
            if 'src_ip' in matches or 'dst_ip' in matches:
                return 'IPV4ANY'
            elif 'src_ipv6' in matches or 'dst_ipv6' in matches:
                return 'IPV6ANY'
            else:
                return 'IP'

    return None


def parse_acl_rule_l4_port_range(l4_port):
    min = 0
    max = 65535

    if '-' not in l4_port:
        raise click.BadParameter('Invalid L4 port range format: {}'.format(l4_port))

    _min, _max = l4_port.split('-')
    lower = int(_min)
    upper = int(_max)

    if upper < lower or lower < min or upper > max:
        raise click.BadParameter('Invalid L4 port range: {}'.format(l4_port))

    return (lower, upper)


def parse_acl_rule_tcp_flags(tcp_flags):
    tcp_flags_value = 0

    for flag in tcp_flags.split(','):
        flag = flag.upper()

        if flag == "FIN":
            tcp_flags_value |= 0x01
        elif flag == "SYN":
            tcp_flags_value |= 0x02
        elif flag == "RST":
            tcp_flags_value |= 0x04
        elif flag == "PSH":
            tcp_flags_value |= 0x08
        elif flag == "ACK":
            tcp_flags_value |= 0x10
        elif flag == "URG":
            tcp_flags_value |= 0x20
        elif flag == "ECE":
           tcp_flags_value |= 0x40
        elif flag == "CWR":
           tcp_flags_value |= 0x80
        else:
            raise click.BadParameter(
                '{} is not a valid TCP flag, select from\n'.format(flag) +
                '  ["fin", "syn", "rst", "psh", "ack", "urg", "ece", "cwr"]'
            )

    return tcp_flags_value


def validate_acl_rule(config_db, state_db, table_type_name, acl_table_name, rule_config):
    # FIXME: hardcore here for the capability write in aclorch
    qualifies_map = {
        "L3": [
            'ETHER_TYPE',
            'VLAN_ID', 'IP_TYPE',
            'SRC_IP', 'DST_IP', 'ICMP_TYPE', 'ICMP_CODE', 'IP_PROTOCOL',
            'L4_SRC_PORT', 'L4_DST_PORT', 'TCP_FLAGS',
            'L4_SRC_PORT_RANGE', 'L4_DST_PORT_RANGE'
        ],
        "L3V6": [
            'VLAN_ID', 'IP_TYPE',
            'SRC_IPV6', 'DST_IPV6', 'ICMPV6_TYPE', 'ICMPV6_CODE', 'NEXT_HEADER',
            'L4_SRC_PORT', 'L4_DST_PORT', 'TCP_FLAGS',
            'L4_SRC_PORT_RANGE', 'L4_DST_PORT_RANGE',
        ],
        "MIRROR": [
            'ETHER_TYPE',
            'VLAN_ID', 'IP_TYPE',
            'SRC_IP', 'DST_IP', 'ICMP_TYPE', 'ICMP_CODE', 'IP_PROTOCOL',
            'L4_SRC_PORT', 'L4_DST_PORT', 'TCP_FLAGS', 'DSCP',
            'L4_SRC_PORT_RANGE', 'L4_DST_PORT_RANGE'
            'IN_PORTS',
        ],
        "MIRRORV6": [
            'ETHER_TYPE', 'VLAN_ID', 'IP_TYPE', 'SRC_IPV6', 'DST_IPV6',
            'ICMPV6_TYPE', 'ICMPV6_CODE', 'NEXT_HEADER', 'L4_SRC_PORT',
            'L4_DST_PORT', 'TCP_FLAGS', 'DSCP', 'L4_SRC_PORT_RANGE',
            'L4_DST_PORT_RANGE'
        ],
        'MIRROR_DSCP': ['DSCP'],
        'CTRLPLANE': ['SRC_IP', 'DST_IP', 'SRC_IPV6', 'DST_IPV6', 'TCP_FLAGS']
    }

    if table_type_name in ['MIRROR', 'MIRRORV6', 'MIRROR_DSCP']:
        if not rule_config.get('MIRROR_INGRESS_ACTION'):
            raise click.BadParameter('mirror-ingress is required on MIRROR ACL table')

    qualifies = qualifies_map.get(table_type_name)
    if qualifies == None:
        user_table_type = config_db.get_entry('ACL_TABLE_TYPE', table_type_name)
        if user_table_type:
            qualifies = user_table_type.get('matches')
            qualifies = [ q.upper() for q in qualifies ]
        else:
            # ignore other table-type
            return

    for match_key in rule_config:
        if match_key == 'PRIORITY' or 'ACTION' in match_key or 'SET' in match_key:
            continue

        if match_key not in qualifies:
            match_key = match_key.replace('_', ' ').lower()
            raise click.BadParameter('{} is not supported on this ACL table'.format(match_key))

    if rule_config.get('TCP_FLAGS'):
        ip_protocol = rule_config.get('IP_PROTOCOL')
        next_header = rule_config.get('NEXT_HEADER')

        if ((ip_protocol != None and ip_protocol != 6)
                or (next_header != None and next_header != 6)):
            raise click.BadParameter(
                'TCP flags is only supported on IP protocol/next header is TCP'
            )

    if (rule_config.get('ICMP_TYPE') != None
            or rule_config.get('ICMP_CODE') != None):
        ip_protocol = rule_config.get('IP_PROTOCOL')

        if (ip_protocol and ip_protocol != 1):
            raise click.BadParameter(
                'ICMP code/type is only supported on IPv4 protocol is ICMP')

    if (rule_config.get('ICMPV6_TYPE') != None
            or rule_config.get('ICMPV6_CODE') != None):
        next_header = rule_config.get('NEXT_HEADER')

        if (next_header and next_header != 58):
            raise click.BadParameter(
                'ICMPv6 code/type is only supported on IPv6 next header is ICMPv6'
            )

    if (rule_config.get('L4_SRC_PORT') != None
            and rule_config.get('L4_SRC_PORT_RANGE') != None):
        raise click.BadParameter(
            'Please configure either "src-l4-port" or "src-l4-port-range," but not both simultaneously.'
        )

    if (rule_config.get('L4_DST_PORT') != None
            and rule_config.get('L4_DST_PORT_RANGE') != None):
        raise click.BadParameter(
            'Please configure either "dst-l4-port" or "dst-l4-port-range," but not both simultaneously.'
        )

    acl_table_state = state_db.get_entry('ACL_TABLE_TABLE', acl_table_name)
    supported_actions = acl_table_state.get('action_list')
    if supported_actions:
        supported_actions = supported_actions.split(',')

        for action_key in rule_config:
            # Only need check the action attributes
            if 'ACTION' in action_key or 'SET' in action_key:
                if action_key not in supported_actions:
                    action_key = action_key.replace('_', ' ').lower()
                    raise click.BadParameter('{} is not supported on this ACL table.'.format(action_key))


def is_rule_exist(config_db, db_table_name, table_name, priority=None, name=None):
    if name != None:
        rule = config_db.get_entry(db_table_name, '{}|{}'.format(table_name, name))

        if rule != {}:
            return True

    if priority != None:
        rules = config_db.get_table(db_table_name)

        for (_table_name, _name), _rule in rules.items():
            if _table_name == table_name:
                if int(_rule['PRIORITY']) == priority:
                    return True

    return False


def get_rule_name(config_db, db_table_name, table_name, priority):
    rules = config_db.get_table(db_table_name)

    for (_table_name, _name), _rule in rules.items():
        if _table_name == table_name:
            if int(_rule['PRIORITY']) == priority:
                return _name

    return None


#
# 'add' subcommand ('config acl add rule ...')
#
@add.command()
@click.pass_context
@click.argument('table_name', metavar='<table_name>')
@click.argument('action', type=click.Choice(['permit', 'deny']))
@click.option('--priority', type=click.IntRange(1, 10000), required=False, help='The priority of the rule. This is used to determine the order in which rules are evaluated. Higher numbers have higher priority. Minimum: "1". Maximum: "10000". If the value is not specified, a new priority is automatically assigned by adding a delta to the smallest priority such that the new priority is divisible by 10. For example, if the smallest priority is 11, the value will be 10 (delta is 1).')
@click.option('--name', type=str, required=False, help='The name of the rule. If the name is not specified, the name is automatically assigned as priority of the rule.')
@click.option('--vlan-id', type=click.IntRange(1, 4094), help='The VLAN ID of the packet. This is used to match tagged packets. Minimum: "1". Maximum: "4094".')
@click.option('--cos', type=COS_RANGE, help='The VLAN PCP field of the packet. This is used to match tagged packets. Minimum: "0". Maximum: "7".')
@click.option('--dscp', type=DSCP_RANGE, help='The DSCP value of the packet. This is used to match IP packets. Minimum: "0". Maximum: "63".')
@click.option('--ip-protocol', type=click.IntRange(0, 255), help='The IP protocol of the packet. Minimum: "0". Maximum: "255".')
@click.option('--next-header', type=click.IntRange(0, 255), help='The IPv6 next header of the packet. Minimum: "0". Maximum: "255".')
@click.option('--src-ip4', type=str, help='The source IPv4 address of the packet.')
@click.option('--dst-ip4', type=str, help='The destination IPv4 address of the packet.')
@click.option('--src-ip6', type=str, help='The source IPv6 address of the packet.')
@click.option('--dst-ip6', type=str, help='The destination IPv6 address of the packet.')
@click.option('--src-l4-port', type=click.IntRange(0, 65535), help='The source TCP or UDP port of the packet. Minimum: "0". Maximum: "65535".')
@click.option('--dst-l4-port', type=click.IntRange(0, 65535), help='The destination TCP or UDP port of the packet. Minimum: "0". Maximum: "65535".')
@click.option('--src-l4-port-range', type=str, help='The source TCP or UDP port range of the packet, format is "<min>-<max>". Minimum: "0". Maximum: "65535".')
@click.option('--dst-l4-port-range', type=str, help='The destination TCP or UDP port range of the packet, format is "<min>-<max>". Minimum: "0". Maximum: "65535".')
@click.option('--tcp-flags', type=str, help='The TCP flags of the packet, support comma-separated lists. The valid value is "fin", "syn", "rst", "psh", "ack", "urg", "ece" and "cwr".')
@click.option('--icmp-type', type=click.IntRange(0, 255), help='The ICMP type of the packet. Minimum: "0". Maximum: "255".')
@click.option('--icmp-code', type=click.IntRange(0, 255), help='The ICMP code of the packet. Minimum: "0". Maximum: "255".')
@click.option('--icmpv6-type', type=click.IntRange(0, 255), help='The ICMPv6 type of the packet. Minimum: "0". Maximum: "255".')
@click.option('--icmpv6-code', type=click.IntRange(0, 255), help='The ICMPv6 code of the packet. Minimum: "0". Maximum: "255".')
@click.option('--mirror-ingress', type=str, help='The mirror session name. This option is only supported for the ACL table type is MIRROR, MIRRORV6, and MIRROR_DSCP')
def rule(ctx, table_name, action, priority, name,
         vlan_id, cos, dscp, ip_protocol, next_header, src_ip4, dst_ip4,
         src_ip6, dst_ip6, src_l4_port, dst_l4_port, src_l4_port_range,
         dst_l4_port_range, tcp_flags, icmp_type, icmp_code, icmpv6_type,
         icmpv6_code, mirror_ingress):
    """Add ACL rule."""
    db_table_name = 'ACL_RULE'

    config_db = ctx.obj.cfgdb
    state_db = ctx.obj.statedb
    MAX_PRIORITY = 10000

    if priority == None:
        priority = get_next_rule_priority(config_db, table_name, MAX_PRIORITY)
        if priority == None:
            raise click.BadParameter('Priority of the rule cannot be automatically generated. Please specify the priority manually.')
    else:
        if is_rule_exist(config_db, db_table_name, table_name, priority=priority):
            raise click.BadParameter('The rule priority already exists in the table.')

    if name == None:
        name = str(priority)
    else:
        def is_valid_name(_str):
            for s in _str:
                if s not in ACL_RULE_NAME_ALLOWED_CHAR:
                    return False

            return True

        if not is_valid_name(name):
            raise click.BadParameter('The rule name is not valid. Valid characters are alphanumeric (A-Z, a-z, 0-9), hyphen (-), and underscore (_).')

        if len(name) > MAX_ACL_RULE_NAME_LEN:
            raise click.BadParameter('The length of the name exceeds the maximum allowed length.')

        if is_rule_exist(config_db, db_table_name, table_name, name=name):
            raise click.BadParameter('The rule name already exists in the table.')

    asic = asic_info.get_asic_info()

    if vlan_id != None:
        if asic.is_bf:
            raise click.BadParameter('Not support vlan-id on Intel platform.')

    if (src_ip4 or dst_ip4) and (src_ip6 or dst_ip6):
        raise click.BadParameter('IPv4 and IPv6 addresses cannot be specified simultaneously.')

    if src_l4_port_range:
        parse_acl_rule_l4_port_range(src_l4_port_range)

    if dst_l4_port_range:
        parse_acl_rule_l4_port_range(dst_l4_port_range)

    if tcp_flags:
        tcp_flags = parse_acl_rule_tcp_flags(tcp_flags)
        tcp_flags = '0x{:02x}/0x{:02x}'.format(tcp_flags, tcp_flags)

    acl_table = config_db.get_entry('ACL_TABLE', table_name)
    table_type = acl_table.get('type')

    if table_type in ['MIRROR', 'MIRRORV6', 'MIRROR_DSCP'] and action == 'deny':
        raise click.BadParameter('"deny" is not supported on MIRROR ACL table.')
    elif table_type == 'CTRLPLANE':
        raise click.BadParameter('This command does not support adding rules to the CTRLPLANE ACL table.')

    attrs = {
        'VLAN_ID': vlan_id,
        'VLAN_PRI': cos,
        'DSCP': dscp,
        'IP_PROTOCOL': ip_protocol,
        'NEXT_HEADER': next_header,
        'SRC_IP': src_ip4,
        'DST_IP': dst_ip4,
        'SRC_IPV6': src_ip6,
        'DST_IPV6': dst_ip6,
        'L4_SRC_PORT': src_l4_port,
        'L4_DST_PORT': dst_l4_port,
        'L4_SRC_PORT_RANGE': src_l4_port_range,
        'L4_DST_PORT_RANGE': dst_l4_port_range,
        'TCP_FLAGS': tcp_flags,
        'ICMP_TYPE': icmp_type,
        'ICMP_CODE': icmp_code,
        'ICMPV6_TYPE': icmpv6_type,
        'ICMPV6_CODE': icmpv6_code,
    }

    rule_config = {}
    for k, v in attrs.items():
        if v != None:
            rule_config[k] = v

    ip_type = get_ip_type_by_acl_table_type(config_db, table_type)
    if ip_type:
        rule_config['IP_TYPE'] = ip_type

    rule_config['PRIORITY'] = priority

    if table_type in ['MIRROR', 'MIRRORV6', 'MIRROR_DSCP']:
        rule_config['MIRROR_INGRESS_ACTION'] = mirror_ingress
    elif table_type == 'CTRLPLANE':
        rule_config['PACKET_ACTION'] = 'ACCEPT' if action == 'permit' else 'DROP'
    else:
        rule_config['PACKET_ACTION'] = 'FORWARD' if action == 'permit' else 'DROP'

    validate_acl_rule(config_db, state_db, table_type, table_name, rule_config)

    key_name = '{}|{}'.format(table_name, name)
    config_util.create(ctx, db_table_name, key_name, rule_config,
                       state_db_table_name='ACL_RULE_TABLE')


#
# 'remove' subgroup ('config acl remove ...')
#

@acl.group(cls=clicommon.AbbreviationGroup)
def remove():
    """
    Remove ACL configuration.
    """
    pass


#
# 'remove' subcommand ('config acl remove table ...')
#
@remove.command()
@click.pass_context
@click.argument("table_name", metavar="<table_name>")
def table(ctx, table_name):
    """
    Remove ACL table
    """
    # config_db = ConfigDBConnector()
    # config_db.connect()
    config_db = ctx.obj.cfgdb

    rule_keys = config_db.get_keys("ACL_RULE")
    for key in rule_keys:
        if key[0] == table_name:
            config_db.set_entry("ACL_RULE", key, None)

    config_db.set_entry("ACL_TABLE", table_name, None)


#
# 'remove' subcommand ('config acl remove table-type ...')
#
@click.command('table-type')
@click.pass_context
@click.argument('type_name', metavar='<type_name>')
def table_type_remove(ctx, type_name):
    """
    Remove ACL table type
    """
    table_name = 'ACL_TABLE_TYPE'
    config_db = ctx.obj.cfgdb

    config_db.set_entry(table_name, type_name, None)


#
# 'remove' subcommand ('config acl remove rule ...')
#
@remove.command()
@click.pass_context
@click.argument('table_name', metavar='<table_name>')
@click.option('--priority', type=click.IntRange(0, 10000), required=False, help='The priority of the rule.')
@click.option('--name', type=str, required=False, help='The name of the rule.')
def rule(ctx, table_name, priority, name):
    """
    Remove ACL rule
    """

    db_table_name = 'ACL_RULE'
    config_db = ctx.obj.cfgdb

    if priority == None:
        if name == None:
            raise click.BadParameter('Either priority or name must be specified.')

        if not is_rule_exist(config_db, db_table_name, table_name, name=name):
            raise click.BadParameter('The rule name does not exist in the table.')
    else:
        if name != None:
            raise click.BadParameter('Rule priority and name cannot be specified at the same time.')

        name = get_rule_name(config_db, db_table_name, table_name, priority)
        if name == None:
            raise click.BadParameter('The rule priority does not exist in the table.')

    config_db.set_entry(db_table_name, '{}|{}'.format(table_name, name), None)


#
# 'acl update' group
#
@acl.group(cls=clicommon.AbbreviationGroup)
def update():
    """ACL-related configuration tasks"""
    pass


#
# 'full' subcommand
#
@update.command()
@click.argument('file_name', required=True)
@click.option('--table_name', type=click.STRING, required=False)
@click.option('--session_name', type=click.STRING, required=False)
def full(file_name, table_name, session_name):
    """Full update of ACL rules configuration."""
    log.log_info("'acl update full {}' executing...".format(file_name))
    command = ['acl-loader', 'update', 'full', str(file_name)]

    if table_name:
        command.append('--table_name')
        command.append(table_name)

    if session_name:
        command.append('--session_name')
        command.append(session_name)

    clicommon.run_command(command)

#
# 'incremental' subcommand
#
@update.command()
@click.argument('file_name', required=True)
@click.option('--session_name', type=click.STRING, required=False)
def incremental(file_name, session_name):
    """Incremental update of ACL rule configuration."""
    log.log_info("'acl update incremental {}' executing...".format(file_name))
    command = ['acl-loader', 'update', 'incremental', str(file_name)]

    if session_name:
        command.append('--session_name')
        command.append(session_name)

    clicommon.run_command(command)


def is_table_type_supported():
    asic = asic_info.get_asic_info()
    if asic.is_bf:
        return False

    return True


def add_command(config):
    if is_table_type_supported():
        add.add_command(table_type_add)
        remove.add_command(table_type_remove)

    config.add_command(acl)
