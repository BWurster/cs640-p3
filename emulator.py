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
        for i in range(1, len(neigh_parts)):
            if i == len(neigh_parts)-1:
                neigh_parts[i] = neigh_parts[i].strip()
            route_topology[neigh_parts[0]].append(neigh_parts[i])
        curr_line = topology_file.readline()

    return route_topology

def createroutes():
    return 0

def forwardpacket():
    return 0

def buildForwardTable(route_topology, start_node):

    num_nodes = len(route_topology)

    # once we find a next hop it stays the same
    
    confirmed_list = []
    # start by adding start node with cost of 0 and no next node
    confirmed_list.append((start_node, 0, -1))

    # look at LSP of this node (immediate neighbors) and put all its neigbors inthe tentative list
    neighs = route_topology[confirmed_list[0][0]]
    tentative_list = []
    for neigh in neighs:
        tentative_list.append((neigh, confirmed_list[0][1]+1, neigh))

    while (len(confirmed_list) != num_nodes):

        # put lowest cost member of tentative list into confirmed list
        lowest_cost = 9999
        popIndex = -1
        chosen_node = tentative_list[0]
        for pos_node in range(len(tentative_list)):
            if tentative_list[pos_node][1] < lowest_cost:
                lowest_cost = tentative_list[pos_node][1]
                chosen_node = tentative_list[pos_node]
                popIndex = pos_node

        confirmed_list.append(chosen_node)
        tentative_list.pop(popIndex)

        if (len(confirmed_list) == num_nodes):
            break

        # examine the neighbors of the newly confirmed member
        neighs = neighs = route_topology[confirmed_list[-1][0]]

        tentative_list = []
        for neigh in neighs:
            tentative_list.append((neigh, confirmed_list[-1][1]+1, confirmed_list[-1][2]))

    return confirmed_list

    

def change_topology_add(initial_route_topology, route_topology, src_ip, src_port):
    for node in route_topology:
        # the received packet is not currently listed as a neighbor but it was a neighbor in the initial configuration
        if str(src_ip + "," + src_port) not in route_topology[node] and str(src_ip + "," + src_port) in initial_route_topology[node]:
            route_topology[node].append(str(src_ip + "," + src_port))

    # get all the keys
    all_keys = route_topology.keys()

    # reconstruct key for unavailable node
    route_topology[str(src_ip + "," + src_port)] = []

    # only want to append keys that are listed as a neighbor in the initial configuration
    for key in all_keys:
        if key in initial_route_topology[str(src_ip + "," + src_port)]:
            route_topology[str(src_ip + "," + src_port)].append(key)

    return route_topology

def change_topology_remove(node_to_remove, route_topology):
    # removing the node from each node's list of neighbors if it contains it
    for node in route_topology:
        if node_to_remove in route_topology[node]:
            route_topology[node].remove(node_to_remove)

    # remove whole key for that node if it exists
    if node_to_remove in route_topology:
        del route_topology[node_to_remove]

    return route_topology

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
    
    route_topology = readtopology(tracker_file)

    initial_route_topology = route_topology

    print(initial_route_topology)

    # pass in route topology into buildForwardTable to find the forwarding table

    # get the neighbors of the emulators we are currently on
    neighs = route_topology[str(this_ip_addr + "," + args.p)]

    latest_timestamps = []
    # latest timestamps set to current time
    for neigh in neighs:
        latest_timestamps.append((neigh, time.time()))

    largest_seqnumbers = []
    all_keys = route_topology.keys()

    # we need the largest sequence number of the received LinkStateMessages from each node except itself.
    for key in all_keys:
        if key != str(this_ip_addr + "," + args.p):    
            largest_seqnumbers.append([key, -1])


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
                    route_topology = change_topology_add(initial_route_topology, route_topology, src_ip, src_port)

                    # need new forwarding table based on this new topology
                    # forwarding_table = buildForwardTable(route_topology, str(this_ip_addr + "," + args.p))

                    # generate and send new link state message to neighbors

            # If it is a LinkStateMessage, your code should...
            elif full_packet[0] == b'L':
                # unpack base ip, base port, seq num and ttl
                header_no_neigh = struct.unpack("!LHLL", full_packet[0:14])
                base_ip = header_no_neigh[0]
                base_port = header_no_neigh[1]
                seq_num = header_no_neigh[2]
                ttl = header_no_neigh[3]

                # Check the largest sequence number of the sender node to determine whether it is an old message. If it’s an old message, ignore it. 
                if seq_num < largest_seqnumbers[str(base_ip + "," + base_port)][1]:
                    continue

                # If the topology changes, update the route topology and forwarding table stored in this emulator if needed.
                if str(base_ip + "," + base_port) not in route_topology:
                    route_topology = change_topology_add(initial_route_topology, route_topology, src_ip, src_port)

                    # update largest timestamp since it was used
                    for tuple in largest_seqnumbers:
                        if tuple[0] == str(base_ip + "," + base_port):
                            # find index of current tuple
                            index = largest_seqnumbers.index(tuple)
                            # update timestamp for this neighbor
                            largest_seqnumbers[index][1] = seq_num

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

    


    #     if full_packet:
    #         # unpack packet information
    #         header = full_packet[:17]
    #         header = struct.unpack("!BLHLHI", ip_header)
    #         data = full_packet[26:]

    #         priority = ip_header[0]
    #         src_addr = ip_header[1]
    #         src_addr = socket.inet_ntoa(struct.pack("!L", src_addr))
    #         src_port = ip_header[2]
    #         dst_addr = ip_header[3]
    #         dst_addr = socket.inet_ntoa(struct.pack("!L", dst_addr))
    #         dst_port = ip_header[4]
    #         length_udp_and_data = ip_header[5]
    #         packet_type = udp_header[0]
    #         seq_num = udp_header[1]
    #         payload_length = udp_header[2]

    #         # if (packet_type == b'A'):
    #         #     print(f"[EMULATOR] Recieved ACK for SEQ_NUM {socket.ntohl(seq_num)}")
    #         # elif (packet_type == b'D'):
    #         #     print(f"[EMULATOR] Recieved DATA for SEQ_NUM {socket.ntohl(seq_num)}")
    #         # elif (packet_type == b'R'):
    #         #     print(f"[EMULATOR] Recieved REQUEST")


    #         # not valid address
    #         if not link_params:
    #             with open(log, 'a') as lf:
    #                 lf.write(f"[{time.asctime()}] SRC: {src_addr}:{src_port}, DST: {dst_addr}:{dst_port}, Priority: {priority}, Size: {payload_length}, No forwarding entry found.\n")
    #         # add to queue if not full
    #         else:
    #             # print("Queue length:", len(queue[priority-1]))
    #             if (len(queue[priority-1]) >= queue_size):
    #                 # send all end packets if they don't enter queue
    #                 if(packet_type == 'E'):
    #                     # send directly to emulator
    #                     socket_obj.sendto(full_packet, (socket.gethostbyname(link_params[4]), int(link_params[5])))
    #                 with open(log, 'a') as lf:
    #                     lf.write(f"[{time.asctime()}] SRC: {src_addr}:{src_port}, DST: {dst_addr}:{dst_port}, Priority: {priority}, Size: {payload_length}, Priority queue {priority} was full.\n")
    #             #add packet to queue
    #             else:
    #                 queue[priority-1].append(full_packet)
        
    #     if packet:
    #         # get packet info
    #         ip_header = packet[:17]
    #         ip_header = struct.unpack("!BLHLHI", ip_header)
    #         udp_header = packet[17:26]
    #         udp_header = struct.unpack("!cII", udp_header)
    #         data = packet[26:]
    #         priority = ip_header[0]
    #         src_addr = ip_header[1]
    #         src_addr = socket.inet_ntoa(struct.pack("!L", src_addr))
    #         src_port = ip_header[2]
    #         dst_addr = ip_header[3]
    #         dst_addr = socket.inet_ntoa(struct.pack("!L", dst_addr))
    #         dst_port = ip_header[4]
    #         length_udp_and_data = ip_header[5]
    #         packet_type = udp_header[0]
    #         seq_num = udp_header[1]
    #         payload_length = udp_header[2]

    #         # get link parameters based on packet info
    #         send_point = (dst_addr, dst_port)
    #         link_params = static_forwarding_lookup.get(send_point)

    #         # if there is no valid link available, remove packet from queue and log event
    #         if (not link_params):
    #             queue[priority-1].pop(0)
    #             with open(log, 'a') as lf:
    #                 lf.write(f"[{time.asctime()}] SRC: {src_addr}:{src_port}, DST: {dst_addr}:{dst_port}, Priority: {priority}, Size: {payload_length}, Destination not in forwarding table.\n")
    #         # if the rate permits, proceed to send or drop
    #         elif (1000*(time.time() - last_send_time) > int(link_params[6])):
    #             # remove packet from queue
    #             queue[priority-1].pop(0)
    #             # send
    #             if(packet_type == b'E' or randint(1, 100) > int(link_params[7])):
    #                 socket_obj.sendto(packet, (socket.gethostbyname(link_params[4]), int(link_params[5])))
    #                 # print(f"[EMULATOR] Sent {packet_type} packet of sequence number {socket.ntohl(seq_num)}")
    #             # drop
    #             else:
    #                 with open(log, 'a') as lf:
    #                     lf.write(f"[{time.asctime()}] SRC: {src_addr}:{src_port}, DST: {dst_addr}:{dst_port}, Priority: {priority}, Size: {payload_length}, loss event occurred.\n")
    #                 # print(f"[EMULATOR] Dropped {packet_type} packet of sequence number {socket.ntohl(seq_num)}")
    #             # log last send time for use with rate
    #             last_send_time = time.time()

    return 0


if __name__ == "__main__":
    main()
