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

def print_topology(route_topology):
    print("TOPOLOGY")
    for host, neighbors in route_topology.items():
        print(host, end=" ")
        for neighbor in neighbors:
            print(neighbor, end=" ")
        print("")
    print("")

def print_forwarding_table(forwarding_table):
    print("FORWARDING TABLE")
    for host, info in forwarding_table.items():
        if (info[0] != 0):
            print(host, end=" ")
            print(info[1])
    print("")

def createroutes(route_topology, forwarding_table, this_port):
    # get the neighbors of the emulators we are currently on
    neighs = route_topology[f"{this_ip_addr},{this_port}"]

    latest_timestamps = {}
    # latest timestamps set to current time
    for neigh in neighs:
        latest_timestamps[neigh] = time.time()

    largest_seqnumbers = {}

    # Receive packet from network in a non-blocking way. This means that you should not wait/get blocked in the recvfrom function until you get a packet.
    socket_obj.setblocking(False)

    hello_msg_time = time.time()

    # send hello message every second (should be some random hardcoded value)
    hello_msg_timeout = 1

    lsm_time = time.time()
    lsm_timeout = 1

    this_next_seq_num = 1

    while True:
        # recieve packet
        try:
            full_packet, (sender_ip, sender_port) = socket_obj.recvfrom(1024)
        except Exception:
            full_packet = None

        if full_packet:
            # If it is a helloMessage, your code should...
            if full_packet[0] == ord('H'):
                # unpack type, ip, and port
                header = struct.unpack("!BLH", full_packet)
                packet_type = header[0]
                src_ip_num = header[1]
                src_port = header[2]

                src_ip = socket.inet_ntoa(struct.pack("!L", src_ip_num))
                # Update the latest timestamp for receiving the helloMessage from the specific neighbor

                latest_timestamps[f"{src_ip},{src_port}"] = time.time()

                # Check the route topology stored in this emulator. If the sender of helloMessage is from a previously unavailable node, change the route topology and forwarding table stored in this emulator. Then generate and send a new LinkStateMessage to its neighbors.
                if f"{src_ip},{src_port}" not in route_topology:
                    # update route topology by using initial topology to help reconstruct the routes
                    print("1", this_ip_addr, src_ip)
                    route_topology = change_topology_add(route_topology, this_ip_addr, this_port, src_ip, src_port)

                    # need new forwarding table based on this new topology
                    forwarding_table = buildForwardTable(route_topology, f"{this_ip_addr},{this_port}")

                    # print changes
                    print_topology(route_topology)
                    print_forwarding_table(forwarding_table)

                    # generate and send new link state message to neighbors
                    link_state_gen_msg = struct.pack("!cLHLL", b'L', struct.unpack("!L", socket.inet_aton(this_ip_addr))[0], int(this_port), this_next_seq_num, 20)
                    this_next_seq_num += 1
                    link_state_gen_msg += struct.pack("!LHL", src_ip_num, src_port, 1)
                    forwardpacket(route_topology, forwarding_table, link_state_gen_msg, None, None, this_port)

            # If it is a LinkStateMessage, your code should...
            elif full_packet[0] == ord('L'):
                # unpack base ip, base port, seq num and ttl
                header_no_neigh = struct.unpack("!LHLL", full_packet[1:15])
                base_ip_num = header_no_neigh[0]
                base_port = header_no_neigh[1]
                seq_num = header_no_neigh[2]
                ttl = header_no_neigh[3]

                base_ip = socket.inet_ntoa(struct.pack("!L", base_ip_num))

                neighbors = []
                num_neighbors = (len(full_packet) - 15) // 10
                for i in range(num_neighbors):
                    neighbor_struct = full_packet[(10*i+15):(10*i+25)]
                    neighbor_info = struct.unpack("!LHL", neighbor_struct)
                    neighbors.append(f"{socket.inet_ntoa(struct.pack('!L', neighbor_info[0]))},{neighbor_info[1]}")

                # Check the largest sequence number of the sender node to determine whether it is an old message. If it’s an old message, ignore it. If not in record, add to record.
                base_id = f"{base_ip},{base_port}"
                if base_id in largest_seqnumbers:
                    if seq_num > largest_seqnumbers[base_id]:
                        largest_seqnumbers[base_id] = seq_num
                        # If the topology changes, update the route topology and forwarding table stored in this emulator if needed.
                        route_topology, hasChanged = check_and_update_topology(route_topology, base_id, neighbors, f"{this_ip_addr},{this_port}")

                        if hasChanged:
                            # need new forwarding table based on this new topology
                            forwarding_table = buildForwardTable(route_topology, f"{this_ip_addr},{this_port}")

                            # print changes
                            print_topology(route_topology)
                            print_forwarding_table(forwarding_table)

                            # Call forwardpacket function to make a process of flooding the LinkStateMessage to its own neighbors.
                            forwardpacket(route_topology, forwarding_table, full_packet, sender_ip, sender_port, this_port)
                else:
                    largest_seqnumbers[base_id] = seq_num

            # If it is a DataPacket / EndPacket / RequestPacket in Lab 2, forward it to the nexthop (figure out the forwarding table to do this).
            elif full_packet[0] == ord('T') or full_packet[0] == ord('R') or full_packet[0] == ord('D') or full_packet[0] == ord('E'):
                forwardpacket(route_topology, forwarding_table, full_packet, None, None, this_port)
            else:
                pass
        
        # things to process regardless
        if (time.time() - hello_msg_time >= hello_msg_timeout):
            # send hello message to all neighbors
            neighs = route_topology[f"{this_ip_addr},{this_port}"]

            for neigh in neighs:
                # has ip address and port
                neigh_info = neigh.split(",")
                hello_msg_packet = struct.pack("!cLH", b'H', struct.unpack("!L", socket.inet_aton(this_ip_addr))[0], int(this_port))
                socket_obj.sendto(hello_msg_packet, (neigh_info[0], int(neigh_info[1])))
            # reset hello message timer
            hello_msg_time = time.time()

        # Check each neighbor, if helloMessage hasn’t received in time (comparing to the latest timestamp of the received HelloMessage from that neighbor), remove the neighbor from route topology, call the buildForwardTable to rebuild the forward table, and update the send new LinkStateMessage to its neighbors.
        keys = list(latest_timestamps.keys()).copy()
        for key in keys:
            # saying that each neighbor must've received the hello message within 1 second (might be incorrect)
            if time.time() - latest_timestamps[key] >= 3*hello_msg_timeout:
                # remove neighbor from topology
                route_topology = change_topology_remove(route_topology, key, f"{this_ip_addr},{this_port}")

                # call the buildForwardTable to rebuild the forward table
                forwarding_table = buildForwardTable(route_topology, f"{this_ip_addr},{this_port}")

                del latest_timestamps[key] # remove from timestamp tracking (no longer exists)

                # print changes
                print_topology(route_topology)
                print_forwarding_table(forwarding_table)

                # update the send new LinkStateMessage to its neighbors
                link_state_gen_msg = struct.pack("!cLHLL", b'L', struct.unpack("!L", socket.inet_aton(this_ip_addr))[0], int(this_port), this_next_seq_num, 20)
                this_next_seq_num += 1
                for neighbor in route_topology[f"{this_ip_addr},{this_port}"]:
                    neighbor_ip = struct.unpack("!L", socket.inet_aton(neighbor.split(",")[0]))[0]
                    neighbor_port = int(neighbor.split(",")[1])
                    link_state_gen_msg += struct.pack("!LHL", neighbor_ip, neighbor_port, 1)
                forwardpacket(route_topology, forwarding_table, link_state_gen_msg, None, None, this_port)

        # Send the newest LinkStateMessage to all neighbors if the defined intervals have passed.
        if (time.time() - lsm_time >= lsm_timeout):
            # update the send new LinkStateMessage to its neighbors
            link_state_gen_msg = struct.pack("!cLHLL", b'L', struct.unpack("!L", socket.inet_aton(this_ip_addr))[0], int(this_port), this_next_seq_num, 20)
            this_next_seq_num += 1
            for neighbor in route_topology[f"{this_ip_addr},{this_port}"]:
                neighbor_ip = struct.unpack("!L", socket.inet_aton(neighbor.split(",")[0]))[0]
                neighbor_port = int(neighbor.split(",")[1])
                link_state_gen_msg += struct.pack("!LHL", neighbor_ip, neighbor_port, 1)
            forwardpacket(route_topology, forwarding_table, link_state_gen_msg, None, None, this_port)
            lsm_time = time.time()

    
    return 0 # will not be reached because createroutes has infinite loop

def forwardpacket(route_topology, forwarding_table, packet, orig_ip, orig_port, this_port):
    if(orig_ip and orig_port):
        orig_id = f"{orig_ip},{orig_port}"
    
    if packet[0] == ord('L'):
        # unpack base ip, base port, seq num and ttl
        mini_struct = struct.unpack("!L", packet[11:15])
        ttl = mini_struct[0]
        packet = packet[0:11] + struct.pack("!L", ttl-1) + packet[15:]

        if ttl > 1:
            neighbors = route_topology[f"{this_ip_addr},{this_port}"]
            if(orig_ip and orig_port and orig_id in neighbors):
                neighbors.remove(orig_id)
            
            for neighbor in neighbors:
                n_ip = neighbor.split(",")[0]
                n_port = int(neighbor.split(",")[1])
                socket_obj.sendto(packet, (n_ip, n_port))

    elif packet[0] == ord('T'):
        rt_packet = struct.unpack("!cLLHLH", packet)
        ttl_in = rt_packet[1]
        rt_src_ip_num = rt_packet[2]
        rt_src_port = rt_packet[3]
        rt_dst_ip_num = rt_packet[4]
        rt_dst_port = rt_packet[5]

        rt_src_ip = socket.inet_ntoa(struct.pack("!L", rt_src_ip_num))
        rt_dst_ip = socket.inet_ntoa(struct.pack("!L", rt_dst_ip_num))
        
        # decide whether to forward based on 
        if ttl_in > 0: # send to next hop
            # read forwarding table
            dst_id = f"{rt_dst_ip},{rt_dst_port}"
            next_hop = forwarding_table[dst_id][1]
            next_ip = next_hop.split(",")[0]
            next_port = int(next_hop.split(",")[1])

            # decrement ttl
            packet = packet[:1] + struct.pack("!L", ttl_in-1) + packet[5:]

            # send
            socket_obj.sendto(packet, (next_ip, next_port))
            pass
        else:
            # return to src = RT node
            rt_ip = rt_src_ip
            rt_port = rt_src_port

            # overwrite source ip and src port
            packet = packet[0:5] + struct.pack("!L", struct.unpack("!L", socket.inet_aton(this_ip_addr))[0]) + struct.pack("!H", int(this_port)) + packet[11:]

            socket_obj.sendto(packet, (rt_ip, rt_port))

            pass

    elif packet[0] == ord('R') or packet[0] == ord('D') or packet[0] == ord('E'):
        # do if interested

        pass
    elif packet[0] == ord('H'):
        # should not happen. We don't forward hello packets
        print("Error")
        pass
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
    base_id = f"{base_ip},{base_port}"
    new_id = f"{new_ip},{new_port}"
    
    route_topology = link_nodes(route_topology, base_id, new_id)

    return route_topology

def change_topology_remove(route_topology, node_to_remove, this_id):
    # removing the node from each node's list of neighbors if it contains it
    for node in route_topology:
        if node_to_remove in route_topology[node]:
            route_topology[node].remove(node_to_remove)

    # remove whole key for that node if it exists
    if node_to_remove in route_topology:
        del route_topology[node_to_remove]

    # handle disjoint graph cleanup
    route_topology = clean_route_topology({}, route_topology, this_id)

    return route_topology

def clean_route_topology(route_topology, old_route_topology, item_to_add):
    route_topology[item_to_add] = old_route_topology[item_to_add]
    for item in route_topology[item_to_add]:
        if not item in route_topology:
            route_topology = clean_route_topology(route_topology, old_route_topology, item)
    return route_topology

def check_and_update_topology(route_topology, base_id, neighbors, this_id):
    hasChanged = False

    if base_id in route_topology:
        if not sorted(neighbors) == sorted(route_topology[base_id]):
            hasChanged = True
            # items in neighbors not in topology (new neighbors)
            for neighbor in [neighbor for neighbor in neighbors if neighbor not in route_topology[base_id]]:
                route_topology = link_nodes(route_topology, neighbor, base_id)
            # items in topology not in neighbors (lost neighbors)
            for neighbor in [neighbor for neighbor in route_topology[base_id] if neighbor not in neighbors]:
                route_topology = change_topology_remove(route_topology, neighbor, this_id)
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
    print_topology(route_topology)

    # pass in route topology into buildForwardTable to find the forwarding table
    forwarding_table = buildForwardTable(route_topology=route_topology, start_node=f"{this_ip_addr},{args.p}")
    print_forwarding_table(forwarding_table)

    createroutes(route_topology, forwarding_table, args.p)

    return 0


if __name__ == "__main__":
    main()
