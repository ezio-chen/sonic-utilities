import threading
import datetime
import click


SYNC_CONFIG_TIMEOUT = 10


def create(ctx, table_name, table_key, value, state_db_table_name=None):
    """Create an entry {table_key: value} in table_name and wait for the state
    entry to be created in state_db_table_name in state_db.

    - table_name will be used as the state db table name if state_db_table_name
      is None.
    - If table_key already exists in table_name, an error will be raised.
    """
    config_db = ctx.obj.cfgdb

    # dump error if table_key already exists
    if config_db.get_entry(table_name, table_key):
        raise click.BadParameter(
            "The key \"{}\" already exists in the table \"{}\"."
            .format(table_key, table_name))

    result = _sync_configure_status(ctx, table_name, table_key, value,
                                    state_db_table_name)

    # in case of failure / timeout, remove table_key
    if result.state_code != 0:
        config_db.set_entry(table_name, table_key, None)
        ctx.fail(result.msg)


def update(ctx, table_name, table_key, value, state_db_table_name=None):
    """Update the entry {table_key: value} in table_name and wait for the state
    entry to be set in state_db_table_name in state_db.

    - value will be merged into the original value. That is, keys that appears
      in the original value will be updated. Otherwise, they will be created.
      As for deleting a key in the original value, those keys whose values are 
      None in value will be deleted in the original value.
    - table_name will be used as the state db table name if state_db_table_name
      is None.
    - If table_key does not exist in table_name, it will be created.
    """
    config_db = ctx.obj.cfgdb
    state_db = ctx.obj.statedb

    if state_db_table_name is None:
        state_db_table_name = table_name

    original_value = config_db.get_entry(table_name, table_key)

    # merge value into original_value and filter out pairs whose val is None
    new_value = { key: val
        for key, val in (original_value | value).items()
        if val is not None}

    result = _sync_configure_status(ctx, table_name, table_key, new_value,
                                    state_db_table_name)

    # in case of failure / timeout, resume the value
    if result.state_code != 0:
        config_db.set_entry(table_name, table_key, original_value)
        ctx.fail(result.msg)


def delete(ctx, table_name, table_key):
    """Delete the entry {table_key: value} in table_name

    - If table_key does not exist in table_name, nothing will be done.
    """
    config_db = ctx.obj.cfgdb
    config_db.set_entry(table_name, table_key, None)


def _sync_configure_status(ctx, table_name, table_key, value,
                           state_db_table_name=None):

    config_db = ctx.obj.cfgdb
    state_db = ctx.obj.statedb

    if state_db_table_name == None:
        state_db_table_name = table_name

    pubsub = state_db.get_redis_client(state_db.STATE_DB).pubsub()
    pubsub.psubscribe(
        "__keyspace@{}__:*"
        .format(state_db.get_dbid(state_db.STATE_DB)))

    def set_entry(barrier):
        barrier.wait()
        config_db.set_entry(table_name, table_key, value)

    barrier = threading.Barrier(2)

    th = threading.Thread(target=set_entry, args=(barrier,))
    th.start()

    class Result:
        def __init__(self, state_code, msg=""):
            self.state_code = state_code
            self.msg = "Configuration failed" if (state_code != 0 and not msg) else msg

    timeout_time = (
        datetime.datetime.now()
        + datetime.timedelta(seconds=SYNC_CONFIG_TIMEOUT))

    barrier.wait()

    while True:
        if datetime.datetime.now() > timeout_time:
            ret = Result(1, "Timeout")
            break

        item = pubsub.get_message(timeout=1)
        if item and "type" in item and item["type"] == "pmessage":
            key = item["channel"].split(":", 1)[1]

            try:
                (table, row) = key.split("|", 1)
                if table == state_db_table_name and row == table_key:
                    client = state_db.get_redis_client(state_db.STATE_DB)
                    data = state_db.raw_to_typed(client.hgetall(key))
                    if data.get("status") == "SUCCESS":
                        ret = Result(0)
                        break
                    elif data.get("status") == "FAILURE":
                        ret = Result(1, data.get("message"))
                        break
                    else:
                        continue

            except ValueError:
                pass    #Ignore non table-formated redis entries

    th.join()

    return ret
