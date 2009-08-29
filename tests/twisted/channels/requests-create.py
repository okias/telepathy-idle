
"""
Test creating a channel with the Requests interface
Most of this test was borrowed from a gabble test and modified to fit idle
"""

from idletest import exec_test
from servicetest import EventPattern, call_async, make_channel_proxy
import dbus
import constants as cs

def test(q, bus, conn, stream):
    conn.Connect()
    q.expect('dbus-signal', signal='StatusChanged', args=[0,1])

    nick = 'foo'
    call_async(q, conn, 'RequestHandles', cs.HT_CONTACT, [nick])
    event = q.expect('dbus-return', method='RequestHandles')
    foo_handle = event.value[0][0]

    properties = conn.GetAll(cs.CONN_IFACE_REQUESTS,
            dbus_interface=cs.PROPERTIES_IFACE)
    assert properties.get('Channels') == [], properties['Channels']
    assert ({cs.CHANNEL_TYPE: cs.CHANNEL_TYPE_TEXT,
             cs.TARGET_HANDLE_TYPE: cs.HT_CONTACT,
            },
            [cs.TARGET_HANDLE, cs.TARGET_ID],
           ) in properties.get('RequestableChannelClasses'),\
                     properties['RequestableChannelClasses']

    requestotron = dbus.Interface(conn, cs.CONN_IFACE_REQUESTS)
    request = { cs.CHANNEL_TYPE: cs.CHANNEL_TYPE_TEXT,
                cs.TARGET_HANDLE_TYPE: cs.HT_CONTACT,
                cs.TARGET_ID: nick,
              }
    call_async(q, requestotron, 'CreateChannel', request)

    ret, old_sig, new_sig = q.expect_many(
        EventPattern('dbus-return', method='CreateChannel'),
        EventPattern('dbus-signal', signal='NewChannel'),
        EventPattern('dbus-signal', signal='NewChannels'),
        )

    assert len(ret.value) == 2
    path, emitted_props = ret.value
    assert emitted_props[cs.CHANNEL_TYPE] == cs.CHANNEL_TYPE_TEXT
    assert emitted_props[cs.TARGET_HANDLE_TYPE] == cs.HT_CONTACT
    assert emitted_props[cs.TARGET_HANDLE] == foo_handle
    assert emitted_props[cs.TARGET_ID] == nick
    assert emitted_props[cs.REQUESTED]
    assert emitted_props[cs.INITIATOR_HANDLE] == conn.GetSelfHandle()
    assert emitted_props[cs.INITIATOR_ID] == stream.nick

    assert old_sig.args[0] == ret.value[0]
    assert old_sig.args[1] == cs.CHANNEL_TYPE_TEXT
    assert old_sig.args[2] == cs.HT_CONTACT
    assert old_sig.args[3] == foo_handle
    assert old_sig.args[4] == True      # suppress handler

    assert len(new_sig.args) == 1
    assert len(new_sig.args[0]) == 1        # one channel
    assert len(new_sig.args[0][0]) == 2     # two struct members
    assert new_sig.args[0][0][0] == ret.value[0]
    assert new_sig.args[0][0][1] == ret.value[1]

    properties = conn.GetAll(cs.CONN_IFACE_REQUESTS,
            dbus_interface=cs.PROPERTIES_IFACE)

    assert new_sig.args[0][0] in properties['Channels'], \
            (new_sig.args[0][0], properties['Channels'])

    chan = make_channel_proxy(conn, path, 'Channel')

    stream.sendMessage('PRIVMSG', stream.nick, ":oh hai", prefix=nick)
    q.expect('dbus-signal', signal='Received')

    # Without acknowledging the message, we close the channel:
    chan.Close()

    # It should close and respawn!
    q.expect('dbus-signal', signal='ChannelClosed')
    chans, = q.expect('dbus-signal', signal='NewChannels').args
    assert len(chans) == 1
    new_props = chans[0][1]

    # It should look pretty similar...
    assert new_props[cs.CHANNEL_TYPE] == cs.CHANNEL_TYPE_TEXT
    assert new_props[cs.TARGET_HANDLE_TYPE] == cs.HT_CONTACT
    assert new_props[cs.TARGET_HANDLE] == foo_handle
    assert new_props[cs.TARGET_ID] == nick

    # ...but this time they started it...
    assert not new_props[cs.REQUESTED]
    assert new_props[cs.INITIATOR_HANDLE] == foo_handle
    assert new_props[cs.INITIATOR_ID] == nick

    # ...and it's got some messages in it!
    ms = chan.ListPendingMessages(False, dbus_interface=cs.CHANNEL_TYPE_TEXT)
    assert len(ms) == 1
    assert ms[0][5] == 'oh hai'

    call_async(q, conn, 'Disconnect')
    q.expect('dbus-signal', signal='StatusChanged', args=[2, 1])


if __name__ == "__main__":
    exec_test(test)
