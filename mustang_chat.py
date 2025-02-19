import sys
import socket
import struct
import threading
import time

# global var to track when last packet was sent
last_sent_time = time.time()

def update_last_sent():
    global last_sent_time
    last_sent_time = time.time()

def send_keep_alive(soc, server_address):
    # Keep alive message is type 7 (no additional data)
    msg_type = 7
    packet = struct.pack('!I', msg_type)
    soc.sendto(packet, server_address)
    print("Keep Alive sent.")
    update_last_sent()

def keep_alive_thread(soc, server_address):
    while True:
        time.sleep(5)  # Check every 5 sec.
        # If 60 seconds have passed since last_sent, send a keep alive msg
        if time.time() - last_sent_time >= 60:
            send_keep_alive(soc, server_address)

def send_login(soc, server_address, username):
    # login request = 0
    msg_type = 0
    # Ensure 32 bit
    username_bytes = username.encode('utf-8')[:32]
    # Pack the message in network byte order: ! -> network order, I -> unsigned int (32 bits), 32s -> 32-byte str
    login_packet = struct.pack('!I32s', msg_type, username_bytes)
    soc.sendto(login_packet, server_address)
    print("Login packet sent.")
    update_last_sent()

def send_join(soc, server_address, channel):
    # Message type (join) = 2
    msg_type = 2
    channel_bytes = channel.encode('utf-8')[:32]
    join_packet = struct.pack('!I32s', msg_type, channel_bytes)
    soc.sendto(join_packet, server_address)
    print(f"Join request for packet {channel} sent.")
    update_last_sent()

def handle_server_msg(data):
    """Inspects message type and prints corresponding output to server.
    Intakes raw data from the server."""

    if len(data) < 4:
        print("handle_server_msg: data too short.")
        return
    msg_type = struct.unpack('!I', data[:4])[0]
    if msg_type == 0:
        # say message type
        if len(data) < 4 + 32 + 32 + 64:
            print("handle_server_msg: Malformed say message.")
            return
        # If valid message, extract (a) channel [32 b] (b) username (sender) [32 b], and (c) text [64 b]
        # rstrip(b'\x00') removes trailing null chars from end of strings
        channel = data[4: 36].rstrip(b'\x00').decode('utf-8')
        sender = data[36: 68].rstrip(b'\x00').decode('utf-8')
        text = data[68:132].rstrip(b'\x00').decode('utf-8')
        # Erase current prompt by clearing line
        sys.stdout.write("\r" + " " * 80 + "\r")
        print(f"[{channel}][{sender}]: {text}")
        # Re-display the prompt
        sys.stdout.write("> ")
        sys.stdout.flush()

    elif msg_type == 1:
        # list message
             # 4 bytes type + 4 bytes number + channels
        if len(data) < 8:
            print("handle_server_msg: Malformed list message.")
            return
        num_channels = struct.unpack('!I', data[4:8])[0]
        channels = []
        offset = 8
        for i in range(num_channels):
            if len(data) < offset + 32:
                break
            channel = data[offset: offset + 32].rstrip(b'\x00').decode('utf-8')
            channels.append(channel)
            offset += 32
        sys.stdout.write("\r" + " " * 80 + "\r")
        print("Existing Channels:")
        # Print all channels
        for c in channels:
            print(c)

        # Re-display the prompt
        sys.stdout.write("> ")
        sys.stdout.flush()

    elif msg_type == 2:
        # Who message
            # 4 bytes type + 4 bytes number + 32 bytes channel + users

        if len(data) < 8 + 32:
            print("handle_server_msg: Malformed who message.")
            return
        num_users = struct.unpack('!I', data[4:8])[0]
        channel = data[8:40].rstrip(b'\x00').decode('utf-8')
        users = []
        offset = 40
        for i in range(num_users):
            if len(data) < offset + 32:
                break
            user = data[offset: offset + 32].rstrip(b'\x00').decode('utf-8')
            users.append(user)
            offset += 32
        sys.stdout.write("\r" + " " * 80 + "\r")
        if num_users != 1:
            print(f"{num_users} users on channel '{channel}':")
        else:
            print(f"{num_users} user on channel '{channel}':")

        for u in users:
            print(u)

        # Re-display the prompt
        sys.stdout.write("> ")
        sys.stdout.flush()
    elif msg_type == 3:
        # Error
        # error message: 4 bytes type + 64 bytes error text

        if len(data) < 4 + 64:
            print("handle_server_msg: Malformed error message.")
            return
        error = struct.unpack('!I', data[4:68])[0]
        sys.stdout.write("\r" + " " * 80 + "\r")
        print(f"Error: {error}")

        # Re-display the prompt
        sys.stdout.write("> ")
        sys.stdout.flush()

    else:
        # Unknown message
        sys.stdout.write("\r" + " " * 80 + "\r")
        print(f"Unknown Message type {msg_type} from server.")
        return

def listen_for_server(soc):
    """Thread Function to listen for messages from the server"""
    while True:
        try:
            data, x = soc.recvfrom(1024)
            handle_server_msg(data)
        except Exception as e:
            # Exit quietly
            if hasattr(e, 'errno') and e.errno == 10038:
                break  # Exit the loop silently.
            print(f"listen_for_server: Listening error {e}")
            break

def main():
    if len(sys.argv) != 4:
        print("Usage: python mustang_chat.py <HostName> <PortNum> <Username>")
        exit(0)
    host = sys.argv[1]
    port = int(sys.argv[2])
    username = sys.argv[3]

    # Create UDP socket using SOCK_DGRAM (datagram)
    soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    soc.bind(('', 0)) # bind to any available port
    server_address = (host, port)

    # send the login request
    send_login(soc, server_address, username)
    send_join(soc, server_address, "Common")

    # Keep track of channels user has joined
    active_channel = "Common"
    joined_channels = {"Common"}
    print("Connected to server. You may now type commands or chat messages (\"/\" for help).")

    # Start a thread to listen for server messages
    listener = threading.Thread(target=listen_for_server, args=(soc, ), daemon=True)
    listener.start()

    # Start the keep alive thread
    keep_thread = threading.Thread(target=keep_alive_thread, args=(soc, server_address), daemon=True)
    keep_thread.start()

    while True:
        # Display prompt
        user_input = input("> ").strip()
        sys.stdout.flush()
        if not user_input:
            continue

        # Command handling!
        if user_input.startswith("/"):
            tokens = user_input.split()
            cmd = tokens[0]


            # Help: Print list of commands
            if cmd == "/":
                print("Commands:")
                print("/exit - Exit channels and program.")
                print("/join <ChannelName> - Join channel.")
                print("/leave <ChannelName> - Leave specified channel.")
                print("/list - Display list of all channel names.")
                print("/who <ChannelName> - Display list of users in specified channel.")
                print("/switch <ChannelName> - Switch to specified channel.")
                continue
            # Exit
            elif cmd == "/exit":
                # send logout packet
                logout_packet = struct.pack('!I', 1)
                soc.sendto(logout_packet, server_address)
                print("Exiting...")
                soc.close()
                sys.exit(0)

            # Join channel
            elif cmd == "/join":
                if len(tokens) < 2:
                    print("Usage: /join <ChannelName>")
                    continue
                channel = tokens[1]
                send_join(soc, server_address, channel)
                joined_channels.add(channel)
                active_channel = channel
                print(f"Joined channel '{channel}'.")

            # Leave channel
            elif cmd == "/leave":
                if len(tokens) < 2:
                    print("Usage: /join <ChannelName>")
                    continue
                channel = tokens[1]
                # msg type for leave is 3
                msg_type = 3
                channel_bytes = channel.encode('utf-8')[:32]
                leave_packet = struct.pack('!I32s', msg_type, channel_bytes)
                soc.sendto(leave_packet, server_address)
                if channel in joined_channels:
                    joined_channels.remove(channel)
                if channel == active_channel:
                    active_channel = None
                    print("You have left the active channel. Please join or switch to a channel (\"/\" for help).")
                continue

            # List
            elif cmd == "/list":
                # msg type for list is 5
                msg_type = 5
                list_packet = struct.pack('!I', msg_type)
                soc.sendto(list_packet, server_address)
                continue

            # Who in channel
            elif cmd == "/who":
                if len(tokens) < 2:
                    print("Usage: /who <ChannelName>")
                    continue
                # msg type for who is 6
                channel = tokens[1]
                channel_bytes = channel.encode('utf-8')[:32]
                msg_type = 6
                who_packet = struct.pack('!I32s', msg_type, channel_bytes)
                soc.sendto(who_packet, server_address)
                continue

            # Switch channels
            elif cmd == "/switch":
                if len(tokens) < 2:
                    print("Usage: /switch <ChannelName>")
                    continue
                channel = tokens[1]
                if channel not in joined_channels:
                    print(f"You have not joined channel '{channel}'.")
                else:
                    active_channel = channel
                    print(f"Switched active channel to '{channel}'.")

            else:
                print(f"Unknown command '{cmd}'. To see list of commands, enter \"/\".")

        # Normal chat message (say)
        else:
            if active_channel is None:
                print("Error: Not in active channel. Please Join or switch channels before sending messages.")
                continue
            else:
                # Message type = 4
                msg_type = 4
                channel_bytes = active_channel.encode('utf-8')[:32]
                text_bytes = user_input.encode('utf-8')[:64]
                say_packet = struct.pack('!I32s64s', msg_type, channel_bytes, text_bytes)
                soc.sendto(say_packet, server_address)
                update_last_sent()
if __name__ == '__main__':
        main()