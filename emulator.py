import argparse
import socket
import struct
from datetime import datetime
import time
import os
from random import randint

# create socket object
try:
    socket_obj = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
except:
    print("Socket creation error occurred.")

this_host = socket.gethostname()
this_ip_addr = socket.gethostbyname(this_host)

def readtopology(topology_file):

    route_topology = {}

    curr_line = topology_file.readline()

    # show initial structure based on topology.txt
    while len(curr_line) != 0:
        neigh_parts = curr_line.split(" ")
        route_topology[neigh_parts[0]] = []
        for part in neigh_parts[1:]:
            s_part = part.strip()
            route_topology[neigh_parts[0]].append(s_part)
        curr_line = topology_file.readline()

    return route_topology

def createroutes():
    return 0

def forwardpacket():
    return 0

def buildForwardTable(route_topology, start_node):
    num_nodes = len(route_topology)

    # once we find a next hop it stays the same
    
    confirmed_list = {}
    # start by adding start node with cost of 0 and no next node
    confirmed_list[start_node] =  (0, -1)

    # look at LSP of this node (immediate neighbors) and put all its neigbors inthe tentative list
    root_neighs = route_topology[start_node]
    tentative_list = []
    for neigh in root_neighs:
        tentative_list.append((neigh, 1, neigh))

    while (len(tentative_list) > 0):
        next_node = tentative_list.pop(0)
        next_neighs = route_topology[next_node[0]]

        for neigh in next_neighs:
            if not (neigh in confirmed_list or neigh in [x[0] for x in tentative_list]):
                tentative_list.append((neigh, next_node[1] + 1, next_node[2]))

        confirmed_list[next_node[0]] = (next_node[1], next_node[2])

    return confirmed_list


def link_nodes(route_topology, id_1, id_2):
    # handle one direction
    if id_1 in route_topology:
        if not id_2 in route_topology[id_1]:
            route_topology[id_1].append(id_2)
    else:
        route_topology[id_1] = [id_2]

    # handle other direction
    if id_2 in route_topology:
        if not id_1 in route_topology[id_2]:
            route_topology[id_2].append(id_1)
    else:
        route_topology[id_2] = [id_1]

    return route_topology
    
def unlink_nodes(route_topology, id_1, id_2):
    if id_1 in route_topology:
        if id_2 in route_topology[id_1]:
            route_topology[id_1].remove(id_2)

    if id_2 in route_topology:
        if id_1 in route_topology[id_2]:
            route_topology[id_2].remove(id_1)

    return route_topology

def change_topology_add(route_topology, base_ip, base_port, new_ip, new_port):
    base_id = str(base_ip + "," + base_port)
    new_id = str(new_ip + "," + new_port)
    
    route_topology = link_nodes(route_topology, base_id, new_id)

    return route_topology

def change_topology_remove(route_topology, node_to_remove):
    # removing the node from each node's list of neighbors if it contains it
    for node in route_topology:
        if node_to_remove in route_topology[node]:
            route_topology[node].remove(node_to_remove)

    # remove whole key for that node if it exists
    if node_to_remove in route_topology:
        del route_topology[node_to_remove]

    return route_topology

def check_and_update_topology(route_topology, base_id, neighbors):
    hasChanged = False

    if base_id in route_topology:
        if not sorted(neighbors) == sorted(route_topology[base_id]):
            hasChanged = True
            # items in neighbors not in topology (new neighbors)
            for neighbor in [neighbor for neighbor in neighbors if neighbor not in route_topology[base_id]]:
                route_topology = link_nodes(route_topology, neighbor, base_id)
            # items in topology not in neighbors (lost neighbors)
            for neighbor in [neighbor for neighbor in route_topology[base_id] if neighbor not in neighbors]:
                route_topology = change_topology_remove(route_topology, neighbor)
            # update base_id neighbors
            route_topology[base_id] = neighbors
    else:
        route_topology[base_id] = neighbors
        for neighbor in neighbors:
            link_nodes(route_topology, neighbor, base_id)
        hasChanged = True

    return (route_topology, hasChanged)


def main():

    parser = argparse.ArgumentParser(description="gets emulator data")

    parser.add_argument('-p', metavar='port')
    parser.add_argument('-f', metavar='filename')

    args = parser.parse_args()

    try:
        socket_obj.bind((this_ip_addr, int(args.p)))
    except:
        print("A socket error has occured.")
        return 1

    try:
        tracker_file = open(os.path.dirname(__file__) + "/" + str(args.f), "r")
    except:
        print("A file error has occurred.")
        return 1
    
    # calculate initial route topology
    route_topology = readtopology(tracker_file)

    # pass in route topology into buildForwardTable to find the forwarding table
    forwarding_table = buildForwardTable(route_topology=route_topology, start_node=str(this_ip_addr + "," + args.p))
    print(forwarding_table)

    # get the neighbors of the emulators we are currently on
    neighs = route_topology[str(this_ip_addr + "," + args.p)]

    latest_timestamps = {}
    # latest timestamps set to current time
    for neigh in neighs:
        latest_timestamps[neigh] = time.time()

    largest_seqnumbers = {}

    # Receive packet from network in a non-blocking way. This means that you should not wait/get blocked in the recvfrom function until you get a packet.
    socket_obj.setblocking(False)

    hello_msg_time = time.time()

    # send hello message every second (should be some random hardcoded value)
    hello_msg_timeout = 1000

    while True:
        # recieve packet
        try:
            full_packet, (sender_ip, sender_port) = socket_obj.recvfrom(1024)
        except Exception:
            full_packet = None

        if full_packet:

            # If it is a helloMessage, your code should...
            if full_packet[0] == b'H':
                # unpack type, ip, and port
                header = struct.unpack("!BLH", full_packet)
                type = header[0]
                src_ip = header[1]
                src_port = header[2]

                src_ip = socket.inet_ntoa(struct.pack("!L", src_ip))
                # Update the latest timestamp for receiving the helloMessage from the specific neighbor
                latest_timestamps[str(src_ip + "," + src_port)] = time.time()

                # Check the route topology stored in this emulator. If the sender of helloMessage is from a previously unavailable node, change the route topology and forwarding table stored in this emulator. Then generate and send a new LinkStateMessage to its neighbors.
                if str(src_ip + "," + src_port) not in route_topology:
                    # update route topology by using initial topology to help reconstruct the routes
                    route_topology = change_topology_add(route_topology, this_ip_addr, args.p, src_ip, src_port)

                    # need new forwarding table based on this new topology
                    forwarding_table = buildForwardTable(route_topology, str(this_ip_addr + "," + args.p))

                    # generate and send new link state message to neighbors
                    # TODO

            # If it is a LinkStateMessage, your code should...
            elif full_packet[0] == b'L':
                # unpack base ip, base port, seq num and ttl
                header_no_neigh = struct.unpack("!LHLL", full_packet[0:14])
                base_ip = header_no_neigh[0]
                base_port = header_no_neigh[1]
                seq_num = header_no_neigh[2]
                ttl = header_no_neigh[3]

                neighbors = []
                neighbors_raw = full_packet[14:]
                num_neighbors = (len(full_packet) - 14) // 10
                for i in range(num_neighbors):
                    neighbor_struct = full_packet[14*i:14*i+10]
                    neighbor_info = struct.unpack("!LHL", neighbor_struct)
                    neighbors.append(str(neighbor_info[0] + "," + neighbor_info[1]))

                # Check the largest sequence number of the sender node to determine whether it is an old message. If it’s an old message, ignore it. If not in record, add to record.
                base_id = str(base_ip + "," + base_port)
                if base_id in largest_seqnumbers:
                    if seq_num <= largest_seqnumbers[base_id]:
                        continue # TODO this is concerning
                    else:
                        largest_seqnumbers[base_id] = seq_num
                else:
                    largest_seqnumbers[base_id] = seq_num

                # If the topology changes, update the route topology and forwarding table stored in this emulator if needed.
                route_topology, hasChanged = check_and_update_topology(route_topology, base_id, neighbors)

                # need new forwarding table based on this new topology
                forwarding_table = buildForwardTable(route_topology)

                # Call forwardpacket function to make a process of flooding the LinkStateMessage to its own neighbors.
                # forwardpacket()

            # If it is a DataPacket / EndPacket / RequestPacket in Lab 2, forward it to the nexthop (figure out the forwarding table to do this).
            elif full_packet[0] == b'R' or full_packet[0] == b'D' or full_packet[0] == b'E':
                pass
            # last case (If it is a routetrace packet (described below), refer to the routetrace application part for correct implementation.)
            else:
                pass
        # No packets received case
        else:
            while (time.time() - hello_msg_time < hello_msg_timeout):
                # wait until hello message timeout interval has passed
                pass

            # send hello message to all neighbors
            neighs = route_topology[str(this_ip_addr + "," + args.p)]

            for neigh in neighs:
                # has ip address and port
                neigh_info = neigh.split(",")
                hello_msg_packet = struct.pack("!cLH", b'H', neigh_info[0], neigh_info[1])
                socket_obj.sendto(hello_msg_packet, tuple(neigh_info))
            # reset hello message timer
            hello_msg_time = time.time()

            # *** ordering might be wrong ***
            # Check each neighbor, if helloMessage hasn’t received in time (comparing to the latest timestamp of the received HelloMessage from that neighbor), remove the neighbor from route topology, call the buildForwardTable to rebuild the forward table, and update the send new LinkStateMessage to its neighbors.
            for timestamp in latest_timestamps:
                # saying that each neighbor must've received the hello message within 1 second (might be incorrect)
                if time.time() - timestamp[1] >= hello_msg_timeout:
                    # remove neighbor from topology
                    route_topology = change_topology_remove(timestamp[0], route_topology)

                    # call the buildForwardTable to rebuild the forward table
                    forwarding_table = buildForwardTable(route_topology)

                    # update the send new LinkStateMessage to its neighbors
                    # do later

            # Send the newest LinkStateMessage to all neighbors if the defined intervals have passed.

    return 0


if __name__ == "__main__":
    main()
