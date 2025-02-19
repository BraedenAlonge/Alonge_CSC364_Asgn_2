import sys
import socket
import struct
import threading
import time

# Global data structs
users = {}     # Maps client address -> {"username": str, "last_active": float, "channels": set([...])}
channels = {}  # Maps channel name -> set(client address)

def process_packet(data, address, soc):
    if len(data) < 4:
        print(f"process_packet (0): Malformed packet (data too short): {address}")
        return
    msg_type = struct.unpack('!I', data[:4])[0]
    if msg_type == 0:
        # login request
        if len(data) < 4 + 32:
            print(f"process_packet: Malformed login packet: {address}")
            return
        username = data[4:36].rstrip(b'\x00').decode('utf-8')
        users[address] = {"username":username, "last_active": time.time(), "channels": set()}
        print(f"Login: '{username}' from {address}")

    elif msg_type == 1:
        # logout request
        if address in users:
            username = users[address]["username"]
            print(f"Logout: '{username}' from {address}")

            # Remove user from all channels
            for channel in list(users[address]["channels"]):
                if channel in channels:
                    channels[channel].discard(address)
                    if not channels[channel]:
                        # 'del' deletes objects
                        del channels[channel]
            del users[address]

        else:
            print(f"Logout from unknown {address}")

    elif msg_type == 2:
        # join request
        if len(data) < 4 + 32:
            print(f"process_packet (2): Malformed join packet: {address}")
            return
        channel = data[4:36].rstrip(b'\x00').decode('utf-8')
        if address not in users:
            print(f"Join request from unknown user {address}")
            return
        # add channel to user's record and add user to the chan list
        users[address]["channels"].add(channel)
        if channel not in channels:
            channels[channel] = set()
        channels[channel].add(address)
        print(f"Join: '{users[address]['username']}' joined channel '{channel}'")

    elif msg_type == 3:
        # leave request
        if len(data) < 4 + 32:
            print(f"process_packet (3): Malformed leave packet: {address}")
            return
        channel = data[4:36].rstrip(b'\x00').decode('utf-8')
        if address not in users:
            print(f"Leave request from unknown user {address}")
            return
        users[address]["channels"].discard(channel)
        if channel in channels:
            channels[channel].discard(address)
            if not channels[channel]:
                del channels[channel]
        print(f"Leave: '{users[address]['username']}' left channel '{channel}'")

    elif msg_type == 4:
        # say request
        if len(data) < 4 + 32 + 64:
            print(f"process_packet (4): Malformed say packet: {address}")
            return
        # channel and text to enc later
        channel = data[4:36].rstrip(b'\x00').decode('utf-8')
        text = data[36:100].rstrip(b'\x00').decode('utf-8')
        if address not in users:
            print(f"Say: '{text}' from unknown user {address}")
            return
        # username to enc later
        username = users[address]["username"]
        print(f"Say: [{channel}][{username}]: {text}")

        # Send the say msg to all users!
        # Note: <ljust> aligns the msg to the left with the spec width I input
        if channel in channels:
            channel_bytes = channel.encode('utf-8').ljust(32, b'\x00')
            username_bytes = username.encode('utf-8').ljust(32, b'\x00')
            text_bytes = text.encode('utf-8').ljust(64, b'\x00')
            response = struct.pack('!I32s32s64s', 0, channel_bytes, username_bytes, text_bytes)

            # now, send response to users
            for client_address in channels[channel]:
                soc.sendto(response, client_address)

    elif msg_type == 5:
        # List message request
        # Build a list response: type 1, num of channels, then each channel name
        # in 32 bytes
        num_channels = len(channels)
        response = struct.pack('!II', 1, num_channels)
        for channel in channels:
            response += channel.encode('utf-8').ljust(32, b'\x00')
        soc.sendto(response, address)
        print(f"List: Sent {num_channels} channels to {address}")

    elif msg_type == 6:
        # who req
        if len(data) < 4 + 32:
            print(f"process_packet (6): Malformed who packet: {address}")
            return
        channel = data[4:36].rstrip(b'\x00').decode('utf-8')
        user_set = set()
        if channel in channels:
            for client_addr in channels[channel]:
                if client_addr in users:
                    user_set.add(users[client_addr]["username"])
        user_list = list(user_set)
        num_users = len(user_list)
        channel_bytes = channel.encode('utf-8').ljust(32, b'\x00')
        response = struct.pack('!II32s', 2, num_users, channel_bytes)
        for uname in user_list:
            response += uname.encode('utf-8').ljust(32, b'\x00')
        soc.sendto(response, address)
        print(f"Who: Sent {num_users} users on channel '{channel}' to {address}")

    elif msg_type == 7:
        # Keep alive req
        if address in users:
            print(f"Keep Alive from '{users[address]['username']}' at {address}")

    else:
        print(f"Unknown message type {msg_type} from {address}")

    # Update last active time if user is logged in
    if address in users:
        users[address]["last_active"] = time.time()

def check_timeouts(soc):
        """This function times out the user after 2 mins of inactivity. Note that
        client will also send a logout request"""
        while True:
            # check every 30 sec (No need to check constantly)
            time.sleep(30)
            current_time = time.time()
            for add in list(users.keys()):
                if current_time - users[add]["last_active"] > 120: # 2 min timeout!
                    # remove user from channels
                    for channel in list(users[add]["channels"]):
                        if channel in channels:
                            channels[channel].discard(add)
                            if not channels[channel]:
                                del channels[channel]
                    del users[add]
def main():
    if len(sys.argv) != 3:
        print("Usage: python server.py <HostAddress> <PortNum>")
        sys.exit(0)
    host = sys.argv[1]
    port = int(sys.argv[2])

    soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    soc.bind((host, port))
    print(f"Server running on {host}: {port}")

    # start thread for  inactive users
    timeout_thread = threading.Thread(target=check_timeouts, args=(soc,), daemon=True)
    timeout_thread.start()

    while True:
        try:
            data, addr = soc.recvfrom(1024)
            process_packet(data, addr, soc)
        except Exception as e:
            print(f"Error receiving packet: {e}")

if __name__ == '__main__':
    main()