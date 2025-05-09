Mustang Chat

A program that allows for communication between clients, either on the same device or across devices.
A function is also implemented to timeout the user after 2 minutes of inactivity.
To run, first enable the server:
Usage: python server.py <HostAddress> <PortNum>

Then, clients may join the server:
Usage: python mustang_chat.py <HostName> <PortNum> <Username>

Commands:
/exit: Logout the user and exit the client software.
/join [channel]: Join (subscribe in) the named channel, creating the channel if
it does not exist.
/leave [channel]: Leave the named channel.
/list: List the names of all channels.
/who [channel]: List the users who are on the named channel.
/switch [channel]: Switch to an existing named channel that user has already
joined.
