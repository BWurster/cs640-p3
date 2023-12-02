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

def start(static_forwarding_lookup, queue_size, log):
    socket_obj.setblocking(False)
    queue = [[],[],[]]

    last_send_time = 0

    while True:
        try:
            full_packet, (sender_ip, sender_port) = socket_obj.recvfrom(1024)
        except Exception:
            full_packet = None

        if full_packet:
            # unpack packet information
            ip_header = full_packet[:17]
            ip_header = struct.unpack("!BLHLHI", ip_header)
            udp_header = full_packet[17:26]
            udp_header = struct.unpack("!cII", udp_header)
            data = full_packet[26:]

            priority = ip_header[0]
            src_addr = ip_header[1]
            src_addr = socket.inet_ntoa(struct.pack("!L", src_addr))
            src_port = ip_header[2]
            dst_addr = ip_header[3]
            dst_addr = socket.inet_ntoa(struct.pack("!L", dst_addr))
            dst_port = ip_header[4]
            length_udp_and_data = ip_header[5]
            packet_type = udp_header[0]
            seq_num = udp_header[1]
            payload_length = udp_header[2]

            # if (packet_type == b'A'):
            #     print(f"[EMULATOR] Recieved ACK for SEQ_NUM {socket.ntohl(seq_num)}")
            # elif (packet_type == b'D'):
            #     print(f"[EMULATOR] Recieved DATA for SEQ_NUM {socket.ntohl(seq_num)}")
            # elif (packet_type == b'R'):
            #     print(f"[EMULATOR] Recieved REQUEST")

            # get link params
            link_params = static_forwarding_lookup.get((dst_addr,dst_port))

            # not valid address
            if not link_params:
                with open(log, 'a') as lf:
                    lf.write(f"[{time.asctime()}] SRC: {src_addr}:{src_port}, DST: {dst_addr}:{dst_port}, Priority: {priority}, Size: {payload_length}, No forwarding entry found.\n")
            # add to queue if not full
            else:
                # print("Queue length:", len(queue[priority-1]))
                if (len(queue[priority-1]) >= queue_size):
                    # send all end packets if they don't enter queue
                    if(packet_type == 'E'):
                        # send directly to emulator
                        socket_obj.sendto(full_packet, (socket.gethostbyname(link_params[4]), int(link_params[5])))
                    with open(log, 'a') as lf:
                        lf.write(f"[{time.asctime()}] SRC: {src_addr}:{src_port}, DST: {dst_addr}:{dst_port}, Priority: {priority}, Size: {payload_length}, Priority queue {priority} was full.\n")
                #add packet to queue
                else:
                    queue[priority-1].append(full_packet)

        
        # Process Queue

        # Select packet to process by priority
        packet = None
        if(len(queue[0])):
            packet = queue[0][0]
        elif(len(queue[1])):
            packet = queue[1][0]
        elif(len(queue[2])):
            packet = queue[2][0]
        
        if packet:
            # get packet info
            ip_header = packet[:17]
            ip_header = struct.unpack("!BLHLHI", ip_header)
            udp_header = packet[17:26]
            udp_header = struct.unpack("!cII", udp_header)
            data = packet[26:]
            priority = ip_header[0]
            src_addr = ip_header[1]
            src_addr = socket.inet_ntoa(struct.pack("!L", src_addr))
            src_port = ip_header[2]
            dst_addr = ip_header[3]
            dst_addr = socket.inet_ntoa(struct.pack("!L", dst_addr))
            dst_port = ip_header[4]
            length_udp_and_data = ip_header[5]
            packet_type = udp_header[0]
            seq_num = udp_header[1]
            payload_length = udp_header[2]

            # get link parameters based on packet info
            send_point = (dst_addr, dst_port)
            link_params = static_forwarding_lookup.get(send_point)

            # if there is no valid link available, remove packet from queue and log event
            if (not link_params):
                queue[priority-1].pop(0)
                with open(log, 'a') as lf:
                    lf.write(f"[{time.asctime()}] SRC: {src_addr}:{src_port}, DST: {dst_addr}:{dst_port}, Priority: {priority}, Size: {payload_length}, Destination not in forwarding table.\n")
            # if the rate permits, proceed to send or drop
            elif (1000*(time.time() - last_send_time) > int(link_params[6])):
                # remove packet from queue
                queue[priority-1].pop(0)
                # send
                if(packet_type == b'E' or randint(1, 100) > int(link_params[7])):
                    socket_obj.sendto(packet, (socket.gethostbyname(link_params[4]), int(link_params[5])))
                    # print(f"[EMULATOR] Sent {packet_type} packet of sequence number {socket.ntohl(seq_num)}")
                # drop
                else:
                    with open(log, 'a') as lf:
                        lf.write(f"[{time.asctime()}] SRC: {src_addr}:{src_port}, DST: {dst_addr}:{dst_port}, Priority: {priority}, Size: {payload_length}, loss event occurred.\n")
                    # print(f"[EMULATOR] Dropped {packet_type} packet of sequence number {socket.ntohl(seq_num)}")
                # log last send time for use with rate
                last_send_time = time.time()

def main():
    parser = argparse.ArgumentParser(description="gets emulator data")

    parser.add_argument('-p', metavar='port')
    parser.add_argument('-q', metavar='queue_size')
    parser.add_argument('-f', metavar='filename')
    parser.add_argument('-l', metavar='log')

    args = parser.parse_args()

    try:
        socket_obj.bind((this_ip_addr, int(args.p)))
    except:
        print("A socket error has occured.")
        return 1

    static_forwarding_lookup = {}

    try:
        static_forwarding_table_file = open(os.path.dirname(__file__) + "/" + str(args.f), "r")
    except:
        print("A file error has occurred.")
        return 1

    matching_host_and_port = (this_host, int(args.p))

    curr_line = static_forwarding_table_file.readline()
    while len(curr_line) != 0:
        split_parts = curr_line.split(" ")
        # check for matching host name and port
        if((split_parts[0], int(split_parts[1])) == matching_host_and_port):
            split_parts[-1] = split_parts[-1].strip()
            # has all the potential destinations of a packet and sees which line matches the packet destination
            static_forwarding_lookup[(socket.gethostbyname(split_parts[2]), int(split_parts[3]))] = split_parts
        curr_line = static_forwarding_table_file.readline()

    start(static_forwarding_lookup, int(args.q), args.l)

    return 0


if __name__ == "__main__":
    main()
